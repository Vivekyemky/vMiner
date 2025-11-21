import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List
from backend.db_manager import (
    DatabaseManager, VCenter, VirtualMachine, HostSystem, Datastore, Cluster,
    DistributedVirtualSwitch, PortGroup, NetworkAdapter, StorageAdapter, ScsiLun,
    ResourcePool, VApp, Folder, Snapshot, VMTemplate, DRSRule,
    VMPerformance, HostPerformance, Event, Alarm, Permission
)
from backend.vcenter_client import VCenterClient

logger = logging.getLogger(__name__)

class SyncEngine:
    """Manages concurrent synchronization of multiple vCenter instances."""
    
    def __init__(self, db_manager: DatabaseManager, max_workers: int = 10):
        self.db_manager = db_manager
        self.max_workers = max_workers
    
    def sync_all_vcenters(self):
        """Sync all active vCenters concurrently."""
        session = self.db_manager.get_local_session()
        vcenters = session.query(VCenter).filter(VCenter.is_active == True).all()
        
        if not vcenters:
            logger.warning("No active vCenters found to sync")
            session.close()
            return
        
        logger.info(f"Starting sync for {len(vcenters)} vCenters")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._sync_vcenter, vc): vc 
                for vc in vcenters
            }
            
            for future in as_completed(futures):
                vcenter = futures[future]
                try:
                    result = future.result()
                    logger.info(f"Sync completed for {vcenter.hostname}: {result}")
                except Exception as e:
                    logger.error(f"Sync failed for {vcenter.hostname}: {e}")
        
        session.close()
        logger.info("All vCenter syncs completed")
    
    def _sync_vcenter(self, vcenter: VCenter):
        """Sync a single vCenter instance with all resource types."""
        session = self.db_manager.get_local_session()
        
        try:
            # Update sync status
            vcenter_obj = session.query(VCenter).filter(VCenter.id == vcenter.id).first()
            vcenter_obj.sync_status = 'syncing'
            session.commit()
            
            # Connect to vCenter
            client = VCenterClient(vcenter.hostname, vcenter.username, vcenter.password)
            if not client.connect():
                raise Exception("Failed to connect to vCenter")
            
            logger.info(f"Starting comprehensive sync for {vcenter.hostname}")
            
            # Track sync statistics
            stats = {}
            
            # ==================== CORE RESOURCES ====================
            logger.info(f"[{vcenter.hostname}] Syncing core resources...")
            
            # Fetch VMs
            vms_data = client.get_all_vms()
            stats['vms'] = len(vms_data)
            
            # Fetch Hosts
            hosts_data = client.get_all_hosts()
            stats['hosts'] = len(hosts_data)
            
            # Fetch Datastores
            datastores_data = client.get_all_datastores()
            stats['datastores'] = len(datastores_data)
            
            # Fetch Clusters
            clusters_data = client.get_all_clusters()
            stats['clusters'] = len(clusters_data)
            
            # ==================== NETWORKING RESOURCES ====================
            logger.info(f"[{vcenter.hostname}] Syncing networking resources...")
            
            # Fetch Distributed vSwitches
            dvs_data = client.get_all_distributed_vswitches()
            stats['dvs'] = len(dvs_data)
            
            # Fetch Port Groups
            port_groups_data = client.get_all_port_groups()
            stats['port_groups'] = len(port_groups_data)
            
            # ==================== RESOURCE MANAGEMENT ====================
            logger.info(f"[{vcenter.hostname}] Syncing resource management...")
            
            # Fetch Resource Pools
            resource_pools_data = client.get_all_resource_pools()
            stats['resource_pools'] = len(resource_pools_data)
            
            # Fetch vApps
            vapps_data = client.get_all_vapps()
            stats['vapps'] = len(vapps_data)
            
            # Fetch Folders
            folders_data = client.get_all_folders()
            stats['folders'] = len(folders_data)
            
            # ==================== TEMPLATES ====================
            logger.info(f"[{vcenter.hostname}] Syncing templates...")
            
            # Fetch VM Templates
            templates_data = client.get_all_vm_templates()
            stats['templates'] = len(templates_data)
            
            # ==================== EVENTS & ALARMS ====================
            logger.info(f"[{vcenter.hostname}] Syncing events and alarms...")
            
            # Fetch Recent Events
            events_data = client.get_recent_events(100)
            stats['events'] = len(events_data)
            
            # Fetch Triggered Alarms
            alarms_data = client.get_triggered_alarms()
            stats['alarms'] = len(alarms_data)
            
            # ==================== PERMISSIONS ====================
            logger.info(f"[{vcenter.hostname}] Syncing permissions...")
            
            # Fetch Permissions
            permissions_data = client.get_permissions()
            stats['permissions'] = len(permissions_data)
            
            # ==================== CLEAR OLD DATA ====================
            logger.info(f"[{vcenter.hostname}] Clearing old data...")
            
            # Clear core resources
            session.query(VirtualMachine).filter(VirtualMachine.vcenter_id == vcenter.id).delete()
            session.query(HostSystem).filter(HostSystem.vcenter_id == vcenter.id).delete()
            session.query(Datastore).filter(Datastore.vcenter_id == vcenter.id).delete()
            session.query(Cluster).filter(Cluster.vcenter_id == vcenter.id).delete()
            
            # Clear networking
            session.query(DistributedVirtualSwitch).filter(DistributedVirtualSwitch.vcenter_id == vcenter.id).delete()
            session.query(PortGroup).filter(PortGroup.vcenter_id == vcenter.id).delete()
            session.query(NetworkAdapter).filter(NetworkAdapter.vcenter_id == vcenter.id).delete()
            
            # Clear storage
            session.query(StorageAdapter).filter(StorageAdapter.vcenter_id == vcenter.id).delete()
            session.query(ScsiLun).filter(ScsiLun.vcenter_id == vcenter.id).delete()
            
            # Clear resource management
            session.query(ResourcePool).filter(ResourcePool.vcenter_id == vcenter.id).delete()
            session.query(VApp).filter(VApp.vcenter_id == vcenter.id).delete()
            session.query(Folder).filter(Folder.vcenter_id == vcenter.id).delete()
            
            # Clear snapshots and templates
            session.query(Snapshot).filter(Snapshot.vcenter_id == vcenter.id).delete()
            session.query(VMTemplate).filter(VMTemplate.vcenter_id == vcenter.id).delete()
            
            # Clear DRS rules
            session.query(DRSRule).filter(DRSRule.vcenter_id == vcenter.id).delete()
            
            # Clear performance (keep last 24 hours only)
            from datetime import timedelta
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            session.query(VMPerformance).filter(
                VMPerformance.vcenter_id == vcenter.id,
                VMPerformance.timestamp < cutoff_time
            ).delete()
            session.query(HostPerformance).filter(
                HostPerformance.vcenter_id == vcenter.id,
                HostPerformance.timestamp < cutoff_time
            ).delete()
            
            # Clear events and alarms
            session.query(Event).filter(Event.vcenter_id == vcenter.id).delete()
            session.query(Alarm).filter(Alarm.vcenter_id == vcenter.id).delete()
            
            # Clear permissions
            session.query(Permission).filter(Permission.vcenter_id == vcenter.id).delete()
            
            session.commit()
            
            # ==================== INSERT NEW DATA ====================
            logger.info(f"[{vcenter.hostname}] Inserting new data...")
            
            # Insert VMs
            for vm_data in vms_data:
                vm = VirtualMachine(vcenter_id=vcenter.id, **vm_data)
                session.add(vm)
            
            # Insert Hosts
            for host_data in hosts_data:
                host = HostSystem(vcenter_id=vcenter.id, **host_data)
                session.add(host)
            
            # Insert Datastores
            for ds_data in datastores_data:
                ds = Datastore(vcenter_id=vcenter.id, **ds_data)
                session.add(ds)
            
            # Insert Clusters
            for cluster_data in clusters_data:
                cluster = Cluster(vcenter_id=vcenter.id, **cluster_data)
                session.add(cluster)
            
            # Insert DVS
            for dvs_item in dvs_data:
                dvs = DistributedVirtualSwitch(vcenter_id=vcenter.id, **dvs_item)
                session.add(dvs)
            
            # Insert Port Groups
            for pg_data in port_groups_data:
                pg = PortGroup(vcenter_id=vcenter.id, **pg_data)
                session.add(pg)
            
            # Insert Resource Pools
            for rp_data in resource_pools_data:
                rp = ResourcePool(vcenter_id=vcenter.id, **rp_data)
                session.add(rp)
            
            # Insert vApps
            for vapp_data in vapps_data:
                vapp = VApp(vcenter_id=vcenter.id, **vapp_data)
                session.add(vapp)
            
            # Insert Folders
            for folder_data in folders_data:
                folder = Folder(vcenter_id=vcenter.id, **folder_data)
                session.add(folder)
            
            # Insert VM Templates
            for template_data in templates_data:
                template = VMTemplate(vcenter_id=vcenter.id, **template_data)
                session.add(template)
            
            # Insert Events
            for event_data in events_data:
                event = Event(vcenter_id=vcenter.id, **event_data)
                session.add(event)
            
            # Insert Alarms
            for alarm_data in alarms_data:
                alarm = Alarm(vcenter_id=vcenter.id, **alarm_data)
                session.add(alarm)
            
            # Insert Permissions
            for perm_data in permissions_data:
                perm = Permission(vcenter_id=vcenter.id, **perm_data)
                session.add(perm)
            
            session.commit()
            
            # ==================== DETAILED RESOURCE COLLECTION ====================
            logger.info(f"[{vcenter.hostname}] Collecting detailed resource data...")
            
            # Get VM objects for detailed collection
            content = client.service_instance.RetrieveContent()
            container_view = content.viewManager.CreateContainerView(
                content.rootFolder, [client.service_instance.content.viewManager.CreateContainerView.__self__.__class__.__bases__[0]], True
            )
            
            # Collect VM-specific data (snapshots, network adapters, performance)
            vm_snapshots_count = 0
            vm_adapters_count = 0
            vm_perf_count = 0
            
            from pyVmomi import vim
            vm_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
            for vm in vm_view.view:
                try:
                    # Snapshots
                    snapshots = client.get_vm_snapshots(vm)
                    for snap_data in snapshots:
                        snap = Snapshot(vcenter_id=vcenter.id, **snap_data)
                        session.add(snap)
                        vm_snapshots_count += 1
                    
                    # Network Adapters
                    adapters = client.get_vm_network_adapters(vm)
                    for adapter_data in adapters:
                        adapter = NetworkAdapter(vcenter_id=vcenter.id, **adapter_data)
                        session.add(adapter)
                        vm_adapters_count += 1
                    
                    # Performance
                    perf_data = client.get_vm_performance(vm)
                    perf = VMPerformance(vcenter_id=vcenter.id, **perf_data)
                    session.add(perf)
                    vm_perf_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error collecting detailed data for VM {vm.name}: {e}")
                    continue
            
            vm_view.Destroy()
            stats['snapshots'] = vm_snapshots_count
            stats['network_adapters'] = vm_adapters_count
            stats['vm_performance'] = vm_perf_count
            
            # Collect Host-specific data (storage adapters, LUNs, performance)
            host_adapters_count = 0
            host_luns_count = 0
            host_perf_count = 0
            
            host_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.HostSystem], True)
            for host in host_view.view:
                try:
                    # Storage Adapters
                    adapters = client.get_host_storage_adapters(host)
                    for adapter_data in adapters:
                        adapter = StorageAdapter(vcenter_id=vcenter.id, **adapter_data)
                        session.add(adapter)
                        host_adapters_count += 1
                    
                    # SCSI LUNs
                    luns = client.get_host_scsi_luns(host)
                    for lun_data in luns:
                        lun = ScsiLun(vcenter_id=vcenter.id, **lun_data)
                        session.add(lun)
                        host_luns_count += 1
                    
                    # Performance
                    perf_data = client.get_host_performance(host)
                    perf = HostPerformance(vcenter_id=vcenter.id, **perf_data)
                    session.add(perf)
                    host_perf_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error collecting detailed data for host {host.name}: {e}")
                    continue
            
            host_view.Destroy()
            stats['storage_adapters'] = host_adapters_count
            stats['scsi_luns'] = host_luns_count
            stats['host_performance'] = host_perf_count
            
            # Collect Cluster-specific data (DRS rules)
            drs_rules_count = 0
            
            cluster_view = content.viewManager.CreateContainerView(content.rootFolder, [vim.ClusterComputeResource], True)
            for cluster in cluster_view.view:
                try:
                    rules = client.get_cluster_drs_rules(cluster)
                    for rule_data in rules:
                        rule = DRSRule(vcenter_id=vcenter.id, **rule_data)
                        session.add(rule)
                        drs_rules_count += 1
                except Exception as e:
                    logger.warning(f"Error collecting DRS rules for cluster {cluster.name}: {e}")
                    continue
            
            cluster_view.Destroy()
            stats['drs_rules'] = drs_rules_count
            
            # Final commit
            session.commit()
            
            # Update vCenter sync status
            vcenter_obj.last_sync = datetime.utcnow()
            vcenter_obj.sync_status = 'completed'
            session.commit()
            
            client.disconnect()
            
            logger.info(f"[{vcenter.hostname}] Sync completed successfully: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing {vcenter.hostname}: {e}")
            vcenter_obj = session.query(VCenter).filter(VCenter.id == vcenter.id).first()
            if vcenter_obj:
                vcenter_obj.sync_status = 'failed'
                session.commit()
            raise
        finally:
            session.close()
    
    def sync_single_vcenter(self, vcenter_id: int):
        """Sync a specific vCenter by ID."""
        session = self.db_manager.get_local_session()
        vcenter = session.query(VCenter).filter(VCenter.id == vcenter_id).first()
        session.close()
        
        if not vcenter:
            raise ValueError(f"vCenter with ID {vcenter_id} not found")
        
        return self._sync_vcenter(vcenter)
