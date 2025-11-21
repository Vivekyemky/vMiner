import logging
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import ssl
from datetime import datetime
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class VCenterClient:
    """Handles connection and data retrieval from vCenter."""
    
    def __init__(self, hostname: str, username: str, password: str):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.service_instance = None
        
    def connect(self):
        """Establish connection to vCenter."""
        try:
            context = ssl._create_unverified_context()
            self.service_instance = SmartConnect(
                host=self.hostname,
                user=self.username,
                pwd=self.password,
                sslContext=context
            )
            logger.info(f"Connected to vCenter: {self.hostname}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.hostname}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from vCenter."""
        if self.service_instance:
            Disconnect(self.service_instance)
            logger.info(f"Disconnected from vCenter: {self.hostname}")
    
    def get_all_vms(self) -> List[Dict[str, Any]]:
        """Retrieve all VMs from vCenter."""
        if not self.service_instance:
            return []
        
        content = self.service_instance.RetrieveContent()
        container = content.rootFolder
        view_type = [vim.VirtualMachine]
        recursive = True
        
        container_view = content.viewManager.CreateContainerView(
            container, view_type, recursive
        )
        
        vms = []
        for vm in container_view.view:
            try:
                vm_data = {
                    'moid': vm._moId,
                    'name': vm.name,
                    'power_state': vm.runtime.powerState if vm.runtime else 'unknown',
                    'cpu_count': vm.config.hardware.numCPU if vm.config else None,
                    'memory_mb': vm.config.hardware.memoryMB if vm.config else None,
                    'guest_full_name': vm.config.guestFullName if vm.config else None,
                    'os_name': vm.guest.guestFullName if vm.guest else None,
                    'ip_address': vm.guest.ipAddress if vm.guest else None,
                    'host': vm.runtime.host.name if vm.runtime and vm.runtime.host else None,
                    'cluster': self._get_cluster_name(vm),
                    'vm_path': vm.config.files.vmPathName if vm.config and vm.config.files else None,
                    'annotation': vm.config.annotation if vm.config else None,
                }
                vms.append(vm_data)
            except Exception as e:
                logger.warning(f"Error processing VM {vm.name}: {e}")
                continue
        
        container_view.Destroy()
        logger.info(f"Retrieved {len(vms)} VMs from {self.hostname}")
        return vms
    
    def get_all_hosts(self) -> List[Dict[str, Any]]:
        """Retrieve all hosts from vCenter."""
        if not self.service_instance:
            return []
        
        content = self.service_instance.RetrieveContent()
        container = content.rootFolder
        view_type = [vim.HostSystem]
        recursive = True
        
        container_view = content.viewManager.CreateContainerView(
            container, view_type, recursive
        )
        
        hosts = []
        for host in container_view.view:
            try:
                host_data = {
                    'moid': host._moId,
                    'name': host.name,
                    'connection_state': host.runtime.connectionState if host.runtime else 'unknown',
                    'power_state': host.runtime.powerState if host.runtime else 'unknown',
                    'cpu_mhz': host.hardware.cpuInfo.hz if host.hardware and host.hardware.cpuInfo else None,
                    'cpu_cores': host.hardware.cpuInfo.numCpuCores if host.hardware and host.hardware.cpuInfo else None,
                    'memory_size': host.hardware.memorySize if host.hardware else None,
                    'vendor': host.hardware.systemInfo.vendor if host.hardware and host.hardware.systemInfo else None,
                    'model': host.hardware.systemInfo.model if host.hardware and host.hardware.systemInfo else None,
                    'cluster': self._get_host_cluster_name(host),
                    'vm_count': len(host.vm) if host.vm else 0,
                }
                hosts.append(host_data)
            except Exception as e:
                logger.warning(f"Error processing host {host.name}: {e}")
                continue
        
        container_view.Destroy()
        logger.info(f"Retrieved {len(hosts)} hosts from {self.hostname}")
        return hosts
    
    def get_all_datastores(self) -> List[Dict[str, Any]]:
        """Retrieve all datastores from vCenter."""
        if not self.service_instance:
            return []
        
        content = self.service_instance.RetrieveContent()
        container = content.rootFolder
        view_type = [vim.Datastore]
        recursive = True
        
        container_view = content.viewManager.CreateContainerView(
            container, view_type, recursive
        )
        
        datastores = []
        for ds in container_view.view:
            try:
                ds_data = {
                    'moid': ds._moId,
                    'name': ds.name,
                    'type': ds.summary.type if ds.summary else None,
                    'capacity': ds.summary.capacity if ds.summary else None,
                    'free_space': ds.summary.freeSpace if ds.summary else None,
                    'uncommitted': ds.summary.uncommitted if ds.summary else None,
                    'accessible': ds.summary.accessible if ds.summary else False,
                    'vm_count': len(ds.vm) if ds.vm else 0,
                }
                datastores.append(ds_data)
            except Exception as e:
                logger.warning(f"Error processing datastore {ds.name}: {e}")
                continue
        
        container_view.Destroy()
        logger.info(f"Retrieved {len(datastores)} datastores from {self.hostname}")
        return datastores
    
    def get_all_clusters(self) -> List[Dict[str, Any]]:
        """Retrieve all clusters from vCenter."""
        if not self.service_instance:
            return []
        
        content = self.service_instance.RetrieveContent()
        container = content.rootFolder
        view_type = [vim.ClusterComputeResource]
        recursive = True
        
        container_view = content.viewManager.CreateContainerView(
            container, view_type, recursive
        )
        
        clusters = []
        for cluster in container_view.view:
            try:
                cluster_data = {
                    'moid': cluster._moId,
                    'name': cluster.name,
                    'total_cpu': cluster.summary.totalCpu if cluster.summary else None,
                    'total_memory': cluster.summary.totalMemory if cluster.summary else None,
                    'num_hosts': cluster.summary.numHosts if cluster.summary else 0,
                    'num_vms': len(cluster.resourcePool.vm) if cluster.resourcePool and cluster.resourcePool.vm else 0,
                    'drs_enabled': cluster.configuration.drsConfig.enabled if cluster.configuration and cluster.configuration.drsConfig else False,
                    'ha_enabled': cluster.configuration.dasConfig.enabled if cluster.configuration and cluster.configuration.dasConfig else False,
                }
                clusters.append(cluster_data)
            except Exception as e:
                logger.warning(f"Error processing cluster {cluster.name}: {e}")
                continue
        
        container_view.Destroy()
        logger.info(f"Retrieved {len(clusters)} clusters from {self.hostname}")
        return clusters
    
    def _get_cluster_name(self, vm) -> str:
        """Get cluster name for a VM."""
        try:
            if vm.runtime and vm.runtime.host:
                host = vm.runtime.host
                if host.parent and isinstance(host.parent, vim.ClusterComputeResource):
                    return host.parent.name
        except:
            pass
        return None
    
    def _get_host_cluster_name(self, host) -> str:
        """Get cluster name for a host."""
        try:
            if host.parent and isinstance(host.parent, vim.ClusterComputeResource):
                return host.parent.name
        except:
            pass
        return None
    
    # ==================== NETWORKING RESOURCES ====================
    
    def get_all_distributed_vswitches(self) -> List[Dict[str, Any]]:
        """Retrieve all Distributed Virtual Switches (DVS)."""
        if not self.service_instance:
            return []
        
        content = self.service_instance.RetrieveContent()
        container = content.rootFolder
        view_type = [vim.DistributedVirtualSwitch]
        recursive = True
        
        container_view = content.viewManager.CreateContainerView(
            container, view_type, recursive
        )
        
        dvs_list = []
        for dvs in container_view.view:
            try:
                dvs_data = {
                    'moid': dvs._moId,
                    'name': dvs.name,
                    'version': dvs.config.productInfo.version if dvs.config and dvs.config.productInfo else None,
                    'num_ports': dvs.config.numPorts if dvs.config else None,
                    'num_uplinks': dvs.config.uplinkPortPolicy.uplinkPortName.__len__() if dvs.config and dvs.config.uplinkPortPolicy else 0,
                    'max_ports': dvs.config.maxPorts if dvs.config else None,
                    'network_io_control_enabled': dvs.config.networkResourceManagementEnabled if dvs.config else False,
                }
                dvs_list.append(dvs_data)
            except Exception as e:
                logger.warning(f"Error processing DVS {dvs.name}: {e}")
                continue
        
        container_view.Destroy()
        logger.info(f"Retrieved {len(dvs_list)} Distributed vSwitches from {self.hostname}")
        return dvs_list
    
    def get_all_port_groups(self) -> List[Dict[str, Any]]:
        """Retrieve all Port Groups (both standard and distributed)."""
        if not self.service_instance:
            return []
        
        content = self.service_instance.RetrieveContent()
        port_groups = []
        
        # Get standard port groups
        container_view = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.Network], True
        )
        
        for network in container_view.view:
            try:
                is_distributed = isinstance(network, vim.dvs.DistributedVirtualPortgroup)
                
                pg_data = {
                    'moid': network._moId,
                    'name': network.name,
                    'is_distributed': is_distributed,
                }
                
                if is_distributed:
                    # Distributed port group
                    if hasattr(network, 'config'):
                        pg_data['vlan_id'] = network.config.defaultPortConfig.vlan.vlanId if hasattr(network.config.defaultPortConfig, 'vlan') else None
                        pg_data['num_ports'] = network.config.numPorts if hasattr(network.config, 'numPorts') else None
                        pg_data['port_binding'] = network.config.type if hasattr(network.config, 'type') else None
                        pg_data['vswitch_name'] = network.config.distributedVirtualSwitch.name if network.config.distributedVirtualSwitch else None
                else:
                    # Standard port group
                    if hasattr(network, 'host') and network.host:
                        host = network.host[0]
                        for pg in host.config.network.portgroup:
                            if pg.spec.name == network.name:
                                pg_data['vlan_id'] = pg.spec.vlanId
                                pg_data['vswitch_name'] = pg.spec.vswitchName
                                break
                
                pg_data['vm_count'] = len(network.vm) if hasattr(network, 'vm') and network.vm else 0
                port_groups.append(pg_data)
                
            except Exception as e:
                logger.warning(f"Error processing port group {network.name}: {e}")
                continue
        
        container_view.Destroy()
        logger.info(f"Retrieved {len(port_groups)} port groups from {self.hostname}")
        return port_groups
    
    def get_vm_network_adapters(self, vm) -> List[Dict[str, Any]]:
        """Get network adapters for a specific VM."""
        adapters = []
        try:
            if vm.config and vm.config.hardware:
                for device in vm.config.hardware.device:
                    if isinstance(device, vim.vm.device.VirtualEthernetCard):
                        adapter_data = {
                            'vm_moid': vm._moId,
                            'adapter_type': type(device).__name__,
                            'mac_address': device.macAddress,
                            'network_name': device.backing.network.name if hasattr(device.backing, 'network') and device.backing.network else None,
                            'connected': device.connectable.connected if device.connectable else False,
                            'start_connected': device.connectable.startConnected if device.connectable else False,
                        }
                        adapters.append(adapter_data)
        except Exception as e:
            logger.warning(f"Error getting network adapters for VM {vm.name}: {e}")
        
        return adapters
    
    # ==================== STORAGE RESOURCES ====================
    
    def get_host_storage_adapters(self, host) -> List[Dict[str, Any]]:
        """Get storage adapters for a specific host."""
        adapters = []
        try:
            if host.config and host.config.storageDevice:
                for hba in host.config.storageDevice.hostBusAdapter:
                    adapter_data = {
                        'host_moid': host._moId,
                        'device': hba.device,
                        'adapter_type': type(hba).__name__,
                        'model': hba.model if hasattr(hba, 'model') else None,
                        'driver': hba.driver if hasattr(hba, 'driver') else None,
                        'pci': hba.pci if hasattr(hba, 'pci') else None,
                        'status': hba.status if hasattr(hba, 'status') else None,
                    }
                    adapters.append(adapter_data)
        except Exception as e:
            logger.warning(f"Error getting storage adapters for host {host.name}: {e}")
        
        return adapters
    
    def get_host_scsi_luns(self, host) -> List[Dict[str, Any]]:
        """Get SCSI LUNs for a specific host."""
        luns = []
        try:
            if host.config and host.config.storageDevice:
                for lun in host.config.storageDevice.scsiLun:
                    lun_data = {
                        'host_moid': host._moId,
                        'canonical_name': lun.canonicalName if hasattr(lun, 'canonicalName') else None,
                        'display_name': lun.displayName if hasattr(lun, 'displayName') else None,
                        'lun_type': lun.lunType if hasattr(lun, 'lunType') else None,
                        'vendor': lun.vendor if hasattr(lun, 'vendor') else None,
                        'model': lun.model if hasattr(lun, 'model') else None,
                        'capacity_mb': int(lun.capacity.block * lun.capacity.blockSize / 1024 / 1024) if hasattr(lun, 'capacity') else None,
                    }
                    
                    # Get multipathing info
                    if hasattr(host.config.storageDevice, 'multipathInfo'):
                        for path_info in host.config.storageDevice.multipathInfo.lun:
                            if path_info.lun == lun.key:
                                lun_data['multipath_policy'] = path_info.policy.policy if hasattr(path_info, 'policy') else None
                                lun_data['path_count'] = len(path_info.path) if hasattr(path_info, 'path') else 0
                                break
                    
                    luns.append(lun_data)
        except Exception as e:
            logger.warning(f"Error getting SCSI LUNs for host {host.name}: {e}")
        
        return luns
    
    # ==================== RESOURCE MANAGEMENT ====================
    
    def get_all_resource_pools(self) -> List[Dict[str, Any]]:
        """Retrieve all Resource Pools."""
        if not self.service_instance:
            return []
        
        content = self.service_instance.RetrieveContent()
        container_view = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.ResourcePool], True
        )
        
        resource_pools = []
        for rp in container_view.view:
            try:
                # Skip root resource pools
                if rp.parent and isinstance(rp.parent, vim.ClusterComputeResource):
                    if rp.name == "Resources":
                        continue
                
                rp_data = {
                    'moid': rp._moId,
                    'name': rp.name,
                    'cluster_moid': rp.owner._moId if hasattr(rp, 'owner') else None,
                    'parent_moid': rp.parent._moId if rp.parent else None,
                    'cpu_reservation': rp.config.cpuAllocation.reservation if rp.config and rp.config.cpuAllocation else None,
                    'cpu_limit': rp.config.cpuAllocation.limit if rp.config and rp.config.cpuAllocation else None,
                    'cpu_shares': rp.config.cpuAllocation.shares.shares if rp.config and rp.config.cpuAllocation and rp.config.cpuAllocation.shares else None,
                    'memory_reservation': rp.config.memoryAllocation.reservation if rp.config and rp.config.memoryAllocation else None,
                    'memory_limit': rp.config.memoryAllocation.limit if rp.config and rp.config.memoryAllocation else None,
                    'memory_shares': rp.config.memoryAllocation.shares.shares if rp.config and rp.config.memoryAllocation and rp.config.memoryAllocation.shares else None,
                    'expandable_reservation': rp.config.cpuAllocation.expandableReservation if rp.config and rp.config.cpuAllocation else False,
                    'vm_count': len(rp.vm) if rp.vm else 0,
                }
                resource_pools.append(rp_data)
            except Exception as e:
                logger.warning(f"Error processing resource pool {rp.name}: {e}")
                continue
        
        container_view.Destroy()
        logger.info(f"Retrieved {len(resource_pools)} resource pools from {self.hostname}")
        return resource_pools
    
    def get_all_vapps(self) -> List[Dict[str, Any]]:
        """Retrieve all vApps."""
        if not self.service_instance:
            return []
        
        content = self.service_instance.RetrieveContent()
        container_view = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualApp], True
        )
        
        vapps = []
        for vapp in container_view.view:
            try:
                vapp_data = {
                    'moid': vapp._moId,
                    'name': vapp.name,
                    'power_state': vapp.runtime.powerState if hasattr(vapp, 'runtime') and vapp.runtime else None,
                    'vm_count': len(vapp.vm) if vapp.vm else 0,
                    'cpu_reservation': vapp.config.cpuAllocation.reservation if vapp.config and vapp.config.cpuAllocation else None,
                    'memory_reservation': vapp.config.memoryAllocation.reservation if vapp.config and vapp.config.memoryAllocation else None,
                }
                vapps.append(vapp_data)
            except Exception as e:
                logger.warning(f"Error processing vApp {vapp.name}: {e}")
                continue
        
        container_view.Destroy()
        logger.info(f"Retrieved {len(vapps)} vApps from {self.hostname}")
        return vapps
    
    def get_all_folders(self) -> List[Dict[str, Any]]:
        """Retrieve all Folders."""
        if not self.service_instance:
            return []
        
        content = self.service_instance.RetrieveContent()
        container_view = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.Folder], True
        )
        
        folders = []
        for folder in container_view.view:
            try:
                # Determine folder type
                folder_type = 'unknown'
                if hasattr(folder, 'childType'):
                    if 'VirtualMachine' in folder.childType:
                        folder_type = 'vm'
                    elif 'ComputeResource' in folder.childType or 'ClusterComputeResource' in folder.childType:
                        folder_type = 'host'
                    elif 'Datastore' in folder.childType:
                        folder_type = 'datastore'
                    elif 'Network' in folder.childType:
                        folder_type = 'network'
                
                folder_data = {
                    'moid': folder._moId,
                    'name': folder.name,
                    'folder_type': folder_type,
                    'parent_moid': folder.parent._moId if folder.parent else None,
                    'path': self._get_folder_path(folder),
                }
                folders.append(folder_data)
            except Exception as e:
                logger.warning(f"Error processing folder {folder.name}: {e}")
                continue
        
        container_view.Destroy()
        logger.info(f"Retrieved {len(folders)} folders from {self.hostname}")
        return folders
    
    def _get_folder_path(self, folder) -> str:
        """Get full path of a folder."""
        path_parts = [folder.name]
        current = folder
        try:
            while current.parent and hasattr(current.parent, 'name'):
                current = current.parent
                if current.name != 'Datacenters':
                    path_parts.insert(0, current.name)
        except:
            pass
        return '/'.join(path_parts)
    
    # ==================== SNAPSHOTS & TEMPLATES ====================
    
    def get_vm_snapshots(self, vm) -> List[Dict[str, Any]]:
        """Get snapshots for a specific VM."""
        snapshots = []
        try:
            if vm.snapshot:
                self._process_snapshot_tree(vm, vm.snapshot.rootSnapshotList, snapshots)
        except Exception as e:
            logger.warning(f"Error getting snapshots for VM {vm.name}: {e}")
        
        return snapshots
    
    def _process_snapshot_tree(self, vm, snapshot_list, snapshots, parent_moid=None):
        """Recursively process snapshot tree."""
        for snapshot in snapshot_list:
            try:
                snapshot_data = {
                    'vm_moid': vm._moId,
                    'snapshot_moid': snapshot.snapshot._moId,
                    'vm_name': vm.name,
                    'snapshot_name': snapshot.name,
                    'description': snapshot.description,
                    'created_date': snapshot.createTime,
                    'quiesced': snapshot.quiesced,
                    'parent_snapshot_moid': parent_moid,
                }
                snapshots.append(snapshot_data)
                
                # Process child snapshots
                if snapshot.childSnapshotList:
                    self._process_snapshot_tree(vm, snapshot.childSnapshotList, snapshots, snapshot.snapshot._moId)
            except Exception as e:
                logger.warning(f"Error processing snapshot: {e}")
                continue
    
    def get_all_vm_templates(self) -> List[Dict[str, Any]]:
        """Retrieve all VM Templates."""
        if not self.service_instance:
            return []
        
        content = self.service_instance.RetrieveContent()
        container_view = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )
        
        templates = []
        for vm in container_view.view:
            try:
                if vm.config and vm.config.template:
                    template_data = {
                        'moid': vm._moId,
                        'name': vm.name,
                        'guest_os': vm.config.guestId if vm.config else None,
                        'cpu_count': vm.config.hardware.numCPU if vm.config else None,
                        'memory_mb': vm.config.hardware.memoryMB if vm.config else None,
                        'num_disks': len([d for d in vm.config.hardware.device if isinstance(d, vim.vm.device.VirtualDisk)]) if vm.config else 0,
                        'folder_moid': vm.parent._moId if vm.parent else None,
                        'annotation': vm.config.annotation if vm.config else None,
                    }
                    templates.append(template_data)
            except Exception as e:
                logger.warning(f"Error processing template {vm.name}: {e}")
                continue
        
        container_view.Destroy()
        logger.info(f"Retrieved {len(templates)} VM templates from {self.hostname}")
        return templates
    
    # ==================== DRS RULES ====================
    
    def get_cluster_drs_rules(self, cluster) -> List[Dict[str, Any]]:
        """Get DRS rules for a specific cluster."""
        rules = []
        try:
            if cluster.configuration and cluster.configuration.rule:
                for rule in cluster.configuration.rule:
                    rule_type = 'unknown'
                    vm_moids = []
                    
                    if isinstance(rule, vim.cluster.AffinityRuleSpec):
                        rule_type = 'affinity'
                        vm_moids = [vm._moId for vm in rule.vm] if rule.vm else []
                    elif isinstance(rule, vim.cluster.AntiAffinityRuleSpec):
                        rule_type = 'anti-affinity'
                        vm_moids = [vm._moId for vm in rule.vm] if rule.vm else []
                    elif isinstance(rule, vim.cluster.VmHostRuleInfo):
                        rule_type = 'vm-host'
                    
                    rule_data = {
                        'cluster_moid': cluster._moId,
                        'rule_name': rule.name,
                        'rule_type': rule_type,
                        'enabled': rule.enabled if hasattr(rule, 'enabled') else False,
                        'mandatory': rule.mandatory if hasattr(rule, 'mandatory') else False,
                        'vm_moids': str(vm_moids),  # Store as JSON string
                    }
                    rules.append(rule_data)
        except Exception as e:
            logger.warning(f"Error getting DRS rules for cluster {cluster.name}: {e}")
        
        return rules
    
    # ==================== PERFORMANCE METRICS ====================
    
    def get_vm_performance(self, vm) -> Dict[str, Any]:
        """Get current performance metrics for a VM."""
        perf_data = {
            'vm_moid': vm._moId,
            'timestamp': datetime.utcnow(),
        }
        
        try:
            if vm.summary and vm.summary.quickStats:
                stats = vm.summary.quickStats
                perf_data['cpu_usage_mhz'] = stats.overallCpuUsage
                perf_data['memory_usage_mb'] = stats.guestMemoryUsage
                perf_data['memory_active_mb'] = stats.hostMemoryUsage
        except Exception as e:
            logger.warning(f"Error getting performance for VM {vm.name}: {e}")
        
        return perf_data
    
    def get_host_performance(self, host) -> Dict[str, Any]:
        """Get current performance metrics for a host."""
        perf_data = {
            'host_moid': host._moId,
            'timestamp': datetime.utcnow(),
        }
        
        try:
            if host.summary and host.summary.quickStats:
                stats = host.summary.quickStats
                perf_data['cpu_usage_mhz'] = stats.overallCpuUsage
                perf_data['memory_usage_mb'] = stats.overallMemoryUsage
        except Exception as e:
            logger.warning(f"Error getting performance for host {host.name}: {e}")
        
        return perf_data
    
    # ==================== EVENTS & ALARMS ====================
    
    def get_recent_events(self, max_events=100) -> List[Dict[str, Any]]:
        """Get recent events from vCenter."""
        if not self.service_instance:
            return []
        
        events = []
        try:
            content = self.service_instance.RetrieveContent()
            event_manager = content.eventManager
            
            # Create filter spec
            filter_spec = vim.event.EventFilterSpec()
            filter_spec.maxCount = max_events
            
            event_list = event_manager.QueryEvents(filter_spec)
            
            for event in event_list:
                event_data = {
                    'event_type': type(event).__name__,
                    'severity': 'info',  # Default
                    'timestamp': event.createdTime,
                    'user_name': event.userName if hasattr(event, 'userName') else None,
                    'entity_moid': event.vm.vm._moId if hasattr(event, 'vm') and event.vm else None,
                    'entity_name': event.vm.name if hasattr(event, 'vm') and event.vm else None,
                    'message': event.fullFormattedMessage if hasattr(event, 'fullFormattedMessage') else str(event),
                }
                events.append(event_data)
        except Exception as e:
            logger.warning(f"Error getting events: {e}")
        
        logger.info(f"Retrieved {len(events)} events from {self.hostname}")
        return events
    
    def get_triggered_alarms(self) -> List[Dict[str, Any]]:
        """Get currently triggered alarms."""
        if not self.service_instance:
            return []
        
        alarms = []
        try:
            content = self.service_instance.RetrieveContent()
            
            # Get all triggered alarms
            for entity in [content.rootFolder]:
                if hasattr(entity, 'triggeredAlarmState'):
                    for alarm_state in entity.triggeredAlarmState:
                        alarm_data = {
                            'alarm_name': alarm_state.alarm.info.name if alarm_state.alarm and alarm_state.alarm.info else 'Unknown',
                            'entity_moid': alarm_state.entity._moId if alarm_state.entity else None,
                            'entity_name': alarm_state.entity.name if hasattr(alarm_state.entity, 'name') else None,
                            'status': alarm_state.overallStatus,
                            'triggered_time': alarm_state.time,
                            'acknowledged': alarm_state.acknowledged if hasattr(alarm_state, 'acknowledged') else False,
                        }
                        alarms.append(alarm_data)
        except Exception as e:
            logger.warning(f"Error getting alarms: {e}")
        
        logger.info(f"Retrieved {len(alarms)} triggered alarms from {self.hostname}")
        return alarms
    
    # ==================== PERMISSIONS ====================
    
    def get_permissions(self) -> List[Dict[str, Any]]:
        """Get permissions from vCenter."""
        if not self.service_instance:
            return []
        
        permissions = []
        try:
            content = self.service_instance.RetrieveContent()
            auth_manager = content.authorizationManager
            
            # Get permissions for root folder
            if hasattr(auth_manager, 'RetrieveEntityPermissions'):
                perms = auth_manager.RetrieveEntityPermissions(content.rootFolder, False)
                
                for perm in perms:
                    perm_data = {
                        'entity_moid': content.rootFolder._moId,
                        'entity_type': 'Folder',
                        'principal': perm.principal,
                        'role_name': self._get_role_name(auth_manager, perm.roleId),
                        'is_group': perm.group,
                        'propagate': perm.propagate,
                    }
                    permissions.append(perm_data)
        except Exception as e:
            logger.warning(f"Error getting permissions: {e}")
        
        logger.info(f"Retrieved {len(permissions)} permissions from {self.hostname}")
        return permissions
    
    def _get_role_name(self, auth_manager, role_id) -> str:
        """Get role name from role ID."""
        try:
            for role in auth_manager.roleList:
                if role.roleId == role_id:
                    return role.name
        except:
            pass
        return f"Role-{role_id}"
