import logging
import re
from rapidfuzz import fuzz, process
from typing import Dict, List, Any, Optional
from backend.db_manager import DatabaseManager, VirtualMachine, HostSystem, Datastore, Cluster
from sqlalchemy import and_, or_

logger = logging.getLogger(__name__)

class QueryEngine:
    """Natural language query engine with fuzzy matching and intent recognition."""
    
    # Keywords for different entity types
    ENTITY_KEYWORDS = {
        'vm': ['vm', 'vms', 'virtual machine', 'virtual machines', 'machine', 'machines'],
        'host': ['host', 'hosts', 'esxi', 'server', 'servers'],
        'datastore': ['datastore', 'datastores', 'storage', 'disk', 'disks'],
        'cluster': ['cluster', 'clusters']
    }
    
    # Action keywords
    ACTION_KEYWORDS = {
        'get': ['get', 'show', 'list', 'find', 'display', 'fetch'],
        'count': ['count', 'how many', 'number of', 'total'],
    }
    
    # State keywords
    STATE_KEYWORDS = {
        'powered_on': ['powered on', 'poweredon', 'running', 'active', 'on'],
        'powered_off': ['powered off', 'poweredoff', 'stopped', 'off', 'shutdown'],
        'empty': ['empty', 'no vms', '0 vms', 'zero vms', 'unused'],
    }
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.last_query_context = {}
    
    def parse_and_execute(self, query: str) -> Dict[str, Any]:
        """Parse natural language query and execute it."""
        query_lower = query.lower()
        
        # Correct spelling using fuzzy matching
        corrected_query = self._correct_spelling(query_lower)
        logger.info(f"Original query: {query}")
        logger.info(f"Corrected query: {corrected_query}")
        
        # Detect entity type
        entity_type = self._detect_entity(corrected_query)
        
        # Detect action
        action = self._detect_action(corrected_query)
        
        # Detect filters
        filters = self._extract_filters(corrected_query, entity_type)
        
        # Execute query
        result = self._execute_query(entity_type, action, filters)
        
        # Store context for follow-up queries
        self.last_query_context = {
            'entity_type': entity_type,
            'filters': filters,
            'result_count': len(result.get('data', []))
        }
        
        return result
    
    def _correct_spelling(self, query: str) -> str:
        """Correct spelling mistakes using fuzzy matching."""
        words = query.split()
        corrected_words = []
        
        # Build a dictionary of all known keywords
        all_keywords = []
        for keywords in self.ENTITY_KEYWORDS.values():
            all_keywords.extend(keywords)
        for keywords in self.ACTION_KEYWORDS.values():
            all_keywords.extend(keywords)
        for keywords in self.STATE_KEYWORDS.values():
            all_keywords.extend(keywords)
        
        for word in words:
            # Check if word is close to any keyword
            match = process.extractOne(word, all_keywords, scorer=fuzz.ratio)
            if match and match[1] > 80:  # 80% similarity threshold
                corrected_words.append(match[0])
            else:
                corrected_words.append(word)
        
        return ' '.join(corrected_words)
    
    def _detect_entity(self, query: str) -> str:
        """Detect the entity type from query."""
        for entity, keywords in self.ENTITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    return entity
        return 'vm'  # Default to VM
    
    def _detect_action(self, query: str) -> str:
        """Detect the action from query."""
        for action, keywords in self.ACTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query:
                    return action
        return 'get'  # Default to get
    
    def _extract_filters(self, query: str, entity_type: str) -> Dict[str, Any]:
        """Extract filters from query."""
        filters = {}
        
        # Power state filters (for VMs)
        if entity_type == 'vm':
            for state, keywords in self.STATE_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in query:
                        if state == 'powered_on':
                            filters['power_state'] = 'poweredOn'
                        elif state == 'powered_off':
                            filters['power_state'] = 'poweredOff'
        
        # Empty datastore filter
        if entity_type == 'datastore':
            for keyword in self.STATE_KEYWORDS['empty']:
                if keyword in query:
                    filters['empty'] = True
        
        # Host with no VMs
        if entity_type == 'host':
            if any(kw in query for kw in ['no vms', '0 vms', 'zero vms', 'empty']):
                filters['no_vms'] = True
        
        # Cluster name extraction
        cluster_match = re.search(r'cluster\s+(\w+)', query)
        if cluster_match:
            filters['cluster'] = cluster_match.group(1)
        
        # Host name extraction
        host_match = re.search(r'host\s+(\w+)', query)
        if host_match:
            filters['host'] = host_match.group(1)
        
        return filters
    
    def _execute_query(self, entity_type: str, action: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual database query."""
        session = self.db_manager.get_local_session()
        
        try:
            if entity_type == 'vm':
                query_obj = session.query(VirtualMachine)
                
                if 'power_state' in filters:
                    query_obj = query_obj.filter(VirtualMachine.power_state == filters['power_state'])
                
                if 'cluster' in filters:
                    query_obj = query_obj.filter(VirtualMachine.cluster.like(f"%{filters['cluster']}%"))
                
                if 'host' in filters:
                    query_obj = query_obj.filter(VirtualMachine.host.like(f"%{filters['host']}%"))
                
                results = query_obj.all()
                
                if action == 'count':
                    return {'count': len(results), 'entity_type': 'vm'}
                
                return {
                    'data': [self._vm_to_dict(vm) for vm in results],
                    'count': len(results),
                    'entity_type': 'vm'
                }
            
            elif entity_type == 'host':
                query_obj = session.query(HostSystem)
                
                if 'no_vms' in filters and filters['no_vms']:
                    query_obj = query_obj.filter(HostSystem.vm_count == 0)
                
                if 'cluster' in filters:
                    query_obj = query_obj.filter(HostSystem.cluster.like(f"%{filters['cluster']}%"))
                
                results = query_obj.all()
                
                if action == 'count':
                    return {'count': len(results), 'entity_type': 'host'}
                
                return {
                    'data': [self._host_to_dict(host) for host in results],
                    'count': len(results),
                    'entity_type': 'host'
                }
            
            elif entity_type == 'datastore':
                query_obj = session.query(Datastore)
                
                if 'empty' in filters and filters['empty']:
                    query_obj = query_obj.filter(Datastore.vm_count == 0)
                
                results = query_obj.all()
                
                if action == 'count':
                    return {'count': len(results), 'entity_type': 'datastore'}
                
                return {
                    'data': [self._datastore_to_dict(ds) for ds in results],
                    'count': len(results),
                    'entity_type': 'datastore'
                }
            
            elif entity_type == 'cluster':
                query_obj = session.query(Cluster)
                results = query_obj.all()
                
                if action == 'count':
                    return {'count': len(results), 'entity_type': 'cluster'}
                
                return {
                    'data': [self._cluster_to_dict(cluster) for cluster in results],
                    'count': len(results),
                    'entity_type': 'cluster'
                }
            
        finally:
            session.close()
    
    def _vm_to_dict(self, vm: VirtualMachine) -> Dict:
        return {
            'id': vm.id,
            'name': vm.name,
            'power_state': vm.power_state,
            'cpu_count': vm.cpu_count,
            'memory_mb': vm.memory_mb,
            'ip_address': vm.ip_address,
            'os_name': vm.os_name,
            'cluster': vm.cluster,
            'host': vm.host,
        }
    
    def _host_to_dict(self, host: HostSystem) -> Dict:
        return {
            'id': host.id,
            'name': host.name,
            'connection_state': host.connection_state,
            'power_state': host.power_state,
            'cpu_cores': host.cpu_cores,
            'memory_size': host.memory_size,
            'cluster': host.cluster,
            'vm_count': host.vm_count,
        }
    
    def _datastore_to_dict(self, ds: Datastore) -> Dict:
        return {
            'id': ds.id,
            'name': ds.name,
            'type': ds.type,
            'capacity': ds.capacity,
            'free_space': ds.free_space,
            'accessible': ds.accessible,
            'vm_count': ds.vm_count,
        }
    
    def _cluster_to_dict(self, cluster: Cluster) -> Dict:
        return {
            'id': cluster.id,
            'name': cluster.name,
            'total_cpu': cluster.total_cpu,
            'total_memory': cluster.total_memory,
            'num_hosts': cluster.num_hosts,
            'num_vms': cluster.num_vms,
            'drs_enabled': cluster.drs_enabled,
            'ha_enabled': cluster.ha_enabled,
        }
