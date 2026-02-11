import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from .connection_manager import ConnectionManager
from .template_engine import TemplateEngine
from .backup import ConfigBackup
from .inventory_loader import InventoryLoader
from .utils import (
    get_logger,
    get_timestamp,
    get_human_timestamp,
    safe_write_file,
    safe_read_file,
    ensure_directory,
    create_progress_bar,
    print_separator,
    print_success,
    print_error,
    print_info,
)
from .exceptions import (
    ConnectionError,
    AuthenticationError,
    TimeoutError,
    CommandExecutionError,
    DeviceNotReachableError,
)


class ConfigDeployment:
    """
    Configuration deployment manager with safety features.

    This class handles deploying configurations to network devices using
    Jinja2 templates. It includes safety features such as automatic
    pre-deployment backups, dry-run mode for testing, and automatic
    rollback on failures.

    Attributes:
        inventory_loader (InventoryLoader): Inventory management instance
        template_engine (TemplateEngine): Template rendering engine
        backup_manager (ConfigBackup): Backup management instance
        logger (logging.Logger): Logger instance for this module
        auto_backup (bool): Whether to automatically backup before deployment

    Example:
        # Initialize deployment manager
        deployer = ConfigDeployment(auto_backup=True)

        # Preview deployment (dry-run)
        device = deployer.inventory_loader.get_device_by_name('spine1')
        variables = {'ntp_server': '10.0.0.1', 'timezone': 'UTC'}
        preview = deployer.preview_deployment(device, 'example_ntp.j2', variables)
        print(preview)

        # Deploy configuration
        result = deployer.deploy_to_device(
            device=device,
            template_name='example_ntp.j2',
            variables=variables,
            dry_run=False
        )

        if result['success']:
            print(f"Deployed successfully to {result['device_name']}")
        else:
            print(f"Deployment failed: {result['error']}")

        # Deploy to multiple devices
        devices = deployer.inventory_loader.get_devices_by_role('spine')
        results = deployer.deploy_to_multiple_devices(
            devices=devices,
            template_name='example_ntp.j2',
            variables={'ntp_server': '10.0.0.1'},
            parallel=True
        )

        # Generate deployment report
        report = deployer.generate_deployment_report(results)
        print(report)
    """

    def __init__(
        self,
        inventory_path: str = "inventory/devices.yaml",
        template_dir: str = "configs/templates",
        auto_backup: bool = True
    ):
        """
        Initialize ConfigDeployment manager.

        Args:
            inventory_path: Path to inventory YAML file (default: inventory/devices.yaml)
            template_dir: Directory containing Jinja2 templates (default: configs/templates)
            auto_backup: Whether to automatically backup before deployment (default: True)

        Raises:
            FileNotFoundError: If inventory file doesn't exist
            Exception: If initialization of any component fails

        Example:
            # Default initialization
            deployer = ConfigDeployment()

            # Custom configuration
            deployer = ConfigDeployment(
                inventory_path="custom/inventory.yaml",
                template_dir="custom/templates",
                auto_backup=True
            )
        """
        self.logger = get_logger(__name__)
        self.auto_backup = auto_backup

        self.logger.info("Initializing ConfigDeployment manager")

        try:
            # Initialize inventory loader
            self.inventory_loader = InventoryLoader(inventory_path)
            self.logger.info(f"Inventory loaded from {inventory_path}")

            # Initialize template engine
            self.template_engine = TemplateEngine(template_dir)
            self.logger.info(f"Template engine initialized with {template_dir}")

            # Initialize backup manager
            self.backup_manager = ConfigBackup(
                inventory_path=inventory_path,
                backup_dir="configs/backups"
            )
            self.logger.info("Backup manager initialized")

            self.logger.info(
                f"ConfigDeployment initialized - "
                f"Auto-backup: {auto_backup}"
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize ConfigDeployment: {e}")
            raise

    def deploy_to_device(
        self,
        device: Dict[str, Any],
        template_name: str,
        variables: Dict[str, Any],
        dry_run: bool = False,
        backup_before: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Deploy configuration to a single device.

        This method renders a configuration template with provided variables
        and deploys it to the target device. It supports dry-run mode for
        testing, automatic pre-deployment backups, and automatic rollback
        on failure.

        Args:
            device: Device dictionary from inventory containing connection details
            template_name: Name of the Jinja2 template file (with or without .j2 extension)
            variables: Dictionary of variables for template rendering
            dry_run: If True, only preview the configuration without deploying (default: False)
            backup_before: Override auto_backup setting (True/False/None to use default)

        Returns:
            Dictionary containing deployment result with keys:
                - success (bool): Whether deployment succeeded
                - device_name (str): Name of the device
                - template_used (str): Template file name
                - backup_created (str or None): Path to backup file if created
                - dry_run (bool): Whether this was a dry-run
                - config_preview (str): Rendered configuration (if dry_run)
                - error (str or None): Error message if deployment failed
                - timestamp (str): Timestamp of deployment attempt
                - output (str or None): Device command output (if deployed)

        Example:
            device = inventory.get_device_by_name('spine1')
            variables = {
                'ntp_server': '10.0.0.1',
                'timezone': 'UTC'
            }

            # Dry-run to preview
            result = deployer.deploy_to_device(
                device=device,
                template_name='example_ntp.j2',
                variables=variables,
                dry_run=True
            )
            print(result['config_preview'])

            # Deploy for real
            result = deployer.deploy_to_device(
                device=device,
                template_name='example_ntp.j2',
                variables=variables,
                dry_run=False
            )

            if result['success']:
                print(f"Success: {result['device_name']}")
            else:
                print(f"Failed: {result['error']}")
        """
        device_name = device.get('name', device.get('ip', 'unknown'))

        result = {
            'success': False,
            'device_name': device_name,
            'template_used': template_name,
            'backup_created': None,
            'dry_run': dry_run,
            'config_preview': None,
            'error': None,
            'timestamp': get_human_timestamp(),
            'output': None
        }

        self.logger.info(
            f"Starting deployment to device '{device_name}' "
            f"(template: {template_name}, dry_run: {dry_run})"
        )

        try:
            # Step 1: Prepare variables for template rendering
            prepared_variables = self._prepare_variables(device, variables)

            # Step 2: Render configuration from template
            self.logger.debug(f"Rendering template '{template_name}' for {device_name}")
            try:
                rendered_config = self.template_engine.render_template(
                    template_name,
                    prepared_variables
                )
            except Exception as e:
                error_msg = f"Template rendering failed: {str(e)}"
                self.logger.error(f"Device '{device_name}': {error_msg}")
                result['error'] = error_msg
                return result

            # Step 3: If dry-run, return preview without deploying
            if dry_run:
                self.logger.info(f"Dry-run mode for '{device_name}' - skipping deployment")
                result['config_preview'] = rendered_config
                result['success'] = True
                return result

            # Step 4: Create backup before deployment if enabled
            should_backup = backup_before if backup_before is not None else self.auto_backup

            if should_backup:
                self.logger.info(f"Creating pre-deployment backup for '{device_name}'")
                try:
                    backup_result = self.backup_manager.backup_device(device, verify=True)

                    if backup_result['success']:
                        result['backup_created'] = backup_result['filepath']
                        self.logger.info(
                            f"Backup created: {os.path.basename(backup_result['filepath'])}"
                        )
                    else:
                        # Backup failed - log warning but continue with deployment
                        # (you can change this to abort if backup is critical)
                        self.logger.warning(
                            f"Pre-deployment backup failed for '{device_name}': "
                            f"{backup_result['error']}"
                        )
                        # Uncomment to abort on backup failure:
                        # result['error'] = f"Backup failed: {backup_result['error']}"
                        # return result

                except Exception as e:
                    self.logger.warning(
                        f"Backup exception for '{device_name}': {e}"
                    )
                    # Continue with deployment even if backup fails

            # Step 5: Merge device settings with global settings
            device_config = self.backup_manager._merge_device_settings(device)

            # Step 6: Connect to device and deploy configuration
            self.logger.info(f"Connecting to device '{device_name}' for deployment")

            try:
                with ConnectionManager(device_config) as conn:
                    self.logger.info(
                        f"Connected to '{device_name}', deploying configuration"
                    )

                    # Split configuration into commands (one per line)
                    # Filter out empty lines and comments
                    config_lines = [
                        line.strip()
                        for line in rendered_config.split('\n')
                        if line.strip() and not line.strip().startswith('!')
                    ]

                    # Deploy configuration using send_config
                    output = conn.send_config(config_lines)
                    result['output'] = output

                    self.logger.info(
                        f"Configuration deployed successfully to '{device_name}'"
                    )
                    result['success'] = True

            except (ConnectionError, AuthenticationError, DeviceNotReachableError) as e:
                error_msg = f"Connection failed: {str(e)}"
                self.logger.error(f"Device '{device_name}': {error_msg}")
                result['error'] = error_msg

                # Attempt rollback if backup was created
                if result['backup_created']:
                    self.logger.warning(
                        f"Attempting rollback for '{device_name}' "
                        f"using backup {result['backup_created']}"
                    )
                    rollback_success = self.rollback_on_failure(
                        device,
                        result['backup_created']
                    )
                    if rollback_success:
                        result['error'] += " (rolled back successfully)"
                    else:
                        result['error'] += " (rollback failed)"

            except CommandExecutionError as e:
                error_msg = f"Configuration deployment failed: {str(e)}"
                self.logger.error(f"Device '{device_name}': {error_msg}")
                result['error'] = error_msg

                # Attempt rollback if backup was created
                if result['backup_created']:
                    self.logger.warning(
                        f"Attempting rollback for '{device_name}' "
                        f"using backup {result['backup_created']}"
                    )
                    rollback_success = self.rollback_on_failure(
                        device,
                        result['backup_created']
                    )
                    if rollback_success:
                        result['error'] += " (rolled back successfully)"
                    else:
                        result['error'] += " (rollback failed)"

            except Exception as e:
                error_msg = f"Unexpected error during deployment: {str(e)}"
                self.logger.error(f"Device '{device_name}': {error_msg}")
                result['error'] = error_msg

        except Exception as e:
            error_msg = f"Deployment process failed: {str(e)}"
            self.logger.error(f"Device '{device_name}': {error_msg}")
            result['error'] = error_msg

        return result

    def deploy_to_multiple_devices(
        self,
        devices: List[Dict[str, Any]],
        template_name: str,
        variables_list: Any,
        dry_run: bool = False,
        parallel: bool = False,
        max_workers: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Deploy configuration to multiple devices.

        Args:
            devices: List of device dictionaries from inventory
            template_name: Name of the Jinja2 template file
            variables_list: Either a single dict to use for all devices,
                          or a list of dicts (one per device)
            dry_run: If True, only preview configurations without deploying
            parallel: If True, deploy to devices in parallel (default: False)
            max_workers: Maximum number of parallel workers (default: 5)

        Returns:
            List of result dictionaries from deploy_to_device()

        Example:
            # Deploy same config to all devices
            devices = inventory.get_devices_by_role('spine')
            results = deployer.deploy_to_multiple_devices(
                devices=devices,
                template_name='example_ntp.j2',
                variables_list={'ntp_server': '10.0.0.1'},
                parallel=True
            )

            # Deploy with device-specific variables
            devices = [spine1, leaf1]
            variables = [
                {'ntp_server': '10.0.0.1', 'priority': 1},
                {'ntp_server': '10.0.0.2', 'priority': 2}
            ]
            results = deployer.deploy_to_multiple_devices(
                devices=devices,
                template_name='example_ntp.j2',
                variables_list=variables,
                parallel=False
            )
        """
        if not devices:
            self.logger.warning("No devices provided for deployment")
            return []

        device_count = len(devices)
        mode = "parallel" if parallel else "sequential"
        self.logger.info(
            f"Starting deployment to {device_count} devices "
            f"(mode: {mode}, dry_run: {dry_run})"
        )

        # Prepare variables list
        # If single dict provided, use same variables for all devices
        if isinstance(variables_list, dict):
            variables_per_device = [variables_list] * device_count
        elif isinstance(variables_list, list):
            if len(variables_list) != device_count:
                self.logger.error(
                    f"Variables list length ({len(variables_list)}) "
                    f"does not match device count ({device_count})"
                )
                # Pad or truncate to match
                if len(variables_list) < device_count:
                    # Use last variable dict for remaining devices
                    last_vars = variables_list[-1] if variables_list else {}
                    variables_per_device = variables_list + [last_vars] * (
                        device_count - len(variables_list)
                    )
                else:
                    variables_per_device = variables_list[:device_count]
            else:
                variables_per_device = variables_list
        else:
            self.logger.error("variables_list must be dict or list of dicts")
            return []

        results = []

        if parallel:
            # Parallel deployment using ThreadPoolExecutor
            self.logger.info(f"Using {max_workers} parallel workers")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all deployment tasks
                future_to_device = {
                    executor.submit(
                        self.deploy_to_device,
                        device,
                        template_name,
                        variables,
                        dry_run
                    ): device
                    for device, variables in zip(devices, variables_per_device)
                }

                # Process results as they complete with progress indicator
                for future in create_progress_bar(
                    as_completed(future_to_device),
                    description="Deploying configurations",
                    total=device_count
                ):
                    try:
                        result = future.result()
                        results.append(result)

                        # Log individual result
                        if result['success']:
                            self.logger.info(
                                f"✓ Deployment successful: {result['device_name']}"
                            )
                        else:
                            self.logger.error(
                                f"✗ Deployment failed: {result['device_name']} "
                                f"- {result['error']}"
                            )

                    except Exception as e:
                        device = future_to_device[future]
                        device_name = device.get('name', 'unknown')
                        self.logger.error(
                            f"Deployment task exception for {device_name}: {e}"
                        )
                        results.append({
                            'success': False,
                            'device_name': device_name,
                            'template_used': template_name,
                            'backup_created': None,
                            'dry_run': dry_run,
                            'config_preview': None,
                            'error': str(e),
                            'timestamp': get_human_timestamp(),
                            'output': None
                        })

        else:
            # Sequential deployment
            for device, variables in zip(
                create_progress_bar(devices, description="Deploying configurations"),
                variables_per_device
            ):
                result = self.deploy_to_device(
                    device,
                    template_name,
                    variables,
                    dry_run
                )
                results.append(result)

                # Log individual result
                if result['success']:
                    self.logger.info(
                        f"✓ Deployment successful: {result['device_name']}"
                    )
                else:
                    self.logger.error(
                        f"✗ Deployment failed: {result['device_name']} "
                        f"- {result['error']}"
                    )

        # Log summary
        success_count = sum(1 for r in results if r['success'])
        failed_count = device_count - success_count

        self.logger.info(
            f"Deployment complete - Total: {device_count}, "
            f"Success: {success_count}, Failed: {failed_count}"
        )

        return results

    def preview_deployment(
        self,
        device: Dict[str, Any],
        template_name: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        Preview configuration that will be deployed (dry-run wrapper).

        Renders the template with variables and formats it with device
        information header for easy review.

        Args:
            device: Device dictionary from inventory
            template_name: Name of the Jinja2 template file
            variables: Dictionary of variables for template rendering

        Returns:
            Formatted preview string with device info and rendered configuration

        Example:
            device = inventory.get_device_by_name('spine1')
            variables = {'ntp_server': '10.0.0.1'}
            preview = deployer.preview_deployment(
                device,
                'example_ntp.j2',
                variables
            )
            print(preview)
        """
        device_name = device.get('name', device.get('ip', 'unknown'))
        device_ip = device.get('ip', 'N/A')
        device_role = device.get('role', 'N/A')

        self.logger.debug(
            f"Generating deployment preview for '{device_name}' "
            f"with template '{template_name}'"
        )

        try:
            # Prepare variables
            prepared_variables = self._prepare_variables(device, variables)

            # Render template
            rendered_config = self.template_engine.render_template(
                template_name,
                prepared_variables
            )

            # Format preview with header
            separator = "=" * 80
            preview = f"""{separator}
DEPLOYMENT PREVIEW
{separator}
Device Name:    {device_name}
Device IP:      {device_ip}
Device Role:    {device_role}
Template:       {template_name}
Generated:      {get_human_timestamp()}
{separator}

{rendered_config}

{separator}
END PREVIEW
{separator}
"""

            return preview

        except Exception as e:
            error_msg = f"Failed to generate preview: {str(e)}"
            self.logger.error(f"Device '{device_name}': {error_msg}")
            return f"ERROR: {error_msg}"

    def verify_deployment(
        self,
        device: Dict[str, Any],
        expected_config: str
    ) -> bool:
        """
        Verify configuration was applied correctly (optional advanced feature).

        Connects to device, retrieves current configuration, and compares
        with expected configuration. This is a basic implementation that
        checks if key configuration lines are present.

        Args:
            device: Device dictionary from inventory
            expected_config: Expected configuration text

        Returns:
            True if configuration matches expectations, False otherwise

        Note:
            This is a basic implementation. For production use, you may want
            to implement more sophisticated comparison logic based on device
            type and configuration structure.

        Example:
            rendered_config = template_engine.render_template(...)
            if deployer.verify_deployment(device, rendered_config):
                print("Configuration verified successfully")
            else:
                print("Configuration verification failed")
        """
        device_name = device.get('name', device.get('ip', 'unknown'))

        self.logger.info(f"Verifying deployment on device '{device_name}'")

        try:
            # Merge device settings
            device_config = self.backup_manager._merge_device_settings(device)

            # Connect and retrieve current config
            with ConnectionManager(device_config) as conn:
                current_config = self.backup_manager._get_device_config(conn, device_config)

                # Extract non-comment, non-empty lines from expected config
                expected_lines = set(
                    line.strip()
                    for line in expected_config.split('\n')
                    if line.strip() and not line.strip().startswith('!')
                )

                # Check if expected lines are present in current config
                missing_lines = []
                for line in expected_lines:
                    if line not in current_config:
                        missing_lines.append(line)

                if missing_lines:
                    self.logger.warning(
                        f"Verification failed for '{device_name}': "
                        f"{len(missing_lines)} lines missing"
                    )
                    for line in missing_lines[:5]:  # Log first 5 missing lines
                        self.logger.debug(f"Missing line: {line}")
                    return False
                else:
                    self.logger.info(
                        f"Verification successful for '{device_name}'"
                    )
                    return True

        except Exception as e:
            self.logger.error(
                f"Verification failed for '{device_name}': {e}"
            )
            return False

    def rollback_on_failure(
        self,
        device: Dict[str, Any],
        backup_filepath: str
    ) -> bool:
        """
        Attempt to restore configuration from backup if deployment fails.

        Connects to the device, loads the backup configuration, and applies it.
        This provides automatic recovery from failed deployments.

        Args:
            device: Device dictionary from inventory
            backup_filepath: Path to backup configuration file

        Returns:
            True if rollback successful, False otherwise

        Example:
            if deployment_failed and backup_created:
                success = deployer.rollback_on_failure(device, backup_filepath)
                if success:
                    print("Successfully rolled back to previous configuration")
        """
        device_name = device.get('name', device.get('ip', 'unknown'))

        self.logger.info(
            f"Attempting rollback for device '{device_name}' "
            f"using backup {backup_filepath}"
        )

        try:
            # Read backup file
            backup_content = safe_read_file(backup_filepath)
            if not backup_content:
                self.logger.error(
                    f"Failed to read backup file: {backup_filepath}"
                )
                return False

            # Remove header comments from backup
            config_lines = [
                line.strip()
                for line in backup_content.split('\n')
                if line.strip() and not line.strip().startswith('#')
            ]

            if not config_lines:
                self.logger.error(
                    f"Backup file contains no configuration: {backup_filepath}"
                )
                return False

            # Merge device settings
            device_config = self.backup_manager._merge_device_settings(device)

            # Connect and apply backup configuration
            with ConnectionManager(device_config) as conn:
                self.logger.info(
                    f"Connected to '{device_name}', applying backup configuration"
                )

                output = conn.send_config(config_lines)

                self.logger.info(
                    f"Rollback successful for '{device_name}'"
                )
                return True

        except Exception as e:
            self.logger.error(
                f"Rollback failed for '{device_name}': {e}"
            )
            return False

    def generate_deployment_report(self, results: List[Dict[str, Any]]) -> str:
        """
        Generate summary report from deployment results.

        Creates a formatted report showing deployment statistics, successful
        deployments, and failed deployments with error details.

        Args:
            results: List of result dictionaries from deployment operations

        Returns:
            Formatted report string

        Example:
            results = deployer.deploy_to_multiple_devices(...)
            report = deployer.generate_deployment_report(results)
            print(report)

            # Save report to file
            safe_write_file("reports/deployment_report.txt", report)
        """
        if not results:
            return "No deployment results to report"

        # Calculate statistics
        total = len(results)
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        dry_run_count = sum(1 for r in results if r.get('dry_run', False))

        success_count = len(successful)
        failed_count = len(failed)

        # Count backups created
        backups_created = sum(
            1 for r in successful if r.get('backup_created')
        )

        # Build report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("CONFIGURATION DEPLOYMENT REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Timestamp:        {get_human_timestamp()}")
        report_lines.append(f"Total devices:    {total}")
        report_lines.append(f"Successful:       {success_count}")
        report_lines.append(f"Failed:           {failed_count}")
        if total > 0:
            report_lines.append(f"Success rate:     {(success_count/total*100):.1f}%")
        if dry_run_count > 0:
            report_lines.append(f"Dry-run count:    {dry_run_count}")
        report_lines.append(f"Backups created:  {backups_created}")
        report_lines.append("")

        # List successful deployments
        if successful:
            report_lines.append("-" * 80)
            report_lines.append("SUCCESSFUL DEPLOYMENTS")
            report_lines.append("-" * 80)
            for r in successful:
                backup_info = ""
                if r.get('backup_created'):
                    backup_info = f" (backup: {os.path.basename(r['backup_created'])})"
                dry_run_info = " [DRY-RUN]" if r.get('dry_run') else ""

                report_lines.append(
                    f"  ✓ {r['device_name']:<15} → {r['template_used']}"
                    f"{backup_info}{dry_run_info}"
                )
            report_lines.append("")

        # List failed deployments
        if failed:
            report_lines.append("-" * 80)
            report_lines.append("FAILED DEPLOYMENTS")
            report_lines.append("-" * 80)
            for r in failed:
                error = r.get('error', 'Unknown error')
                # Truncate long error messages
                if len(error) > 60:
                    error = error[:57] + "..."

                report_lines.append(
                    f"  ✗ {r['device_name']:<15} → {error}"
                )
            report_lines.append("")

        report_lines.append("=" * 80)

        return "\n".join(report_lines)

    def _prepare_variables(
        self,
        device: Dict[str, Any],
        custom_variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge device data with custom variables for template rendering.

        Combines device information (hostname, ip, role, etc.) with
        custom variables. Custom variables override device data if
        there are conflicts. Also adds timestamp automatically.

        Args:
            device: Device dictionary from inventory
            custom_variables: Custom variables provided by user

        Returns:
            Combined variables dictionary ready for template rendering

        Example:
            device = {'name': 'spine1', 'ip': '192.168.1.1', 'role': 'spine'}
            custom_vars = {'ntp_server': '10.0.0.1'}
            variables = self._prepare_variables(device, custom_vars)
            # Returns: {
            #     'name': 'spine1',
            #     'hostname': 'spine1',
            #     'ip': '192.168.1.1',
            #     'role': 'spine',
            #     'ntp_server': '10.0.0.1',
            #     'timestamp': '2025-02-03 14:30:22'
            # }
        """
        # Start with device data
        variables = device.copy()

        # Add hostname alias if not present
        if 'hostname' not in variables and 'name' in variables:
            variables['hostname'] = variables['name']

        # Add timestamp
        variables['timestamp'] = get_human_timestamp()

        # Merge custom variables (override device data if conflict)
        variables.update(custom_variables)

        self.logger.debug(
            f"Prepared {len(variables)} variables for device "
            f"'{device.get('name', 'unknown')}'"
        )

        return variables

    def _validate_template_variables(
        self,
        template_name: str,
        variables: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Check if all required variables are provided for template.

        Extracts variable names from the template and compares with
        provided variables to identify missing required variables.

        Args:
            template_name: Name of the Jinja2 template
            variables: Dictionary of variables to validate

        Returns:
            Tuple of (is_valid, missing_variables):
                - (True, []) if all required variables are present
                - (False, [missing_vars]) if some variables are missing

        Example:
            is_valid, missing = self._validate_template_variables(
                'example_ntp.j2',
                {'hostname': 'spine1', 'ntp_server': '10.0.0.1'}
            )

            if not is_valid:
                print(f"Missing variables: {missing}")
        """
        try:
            # Get required variables from template
            required_vars = self.template_engine.get_template_variables(template_name)

            # Variables that should be automatically provided
            auto_provided = {'timestamp'}

            # Find missing variables
            provided_vars = set(variables.keys())
            missing_vars = list(
                required_vars - provided_vars - auto_provided
            )

            if missing_vars:
                self.logger.warning(
                    f"Template '{template_name}' missing variables: {missing_vars}"
                )
                return (False, missing_vars)
            else:
                self.logger.debug(
                    f"Template '{template_name}' has all required variables"
                )
                return (True, [])

        except Exception as e:
            self.logger.error(
                f"Failed to validate template variables: {e}"
            )
            # On error, assume valid (optimistic)
            return (True, [])

    def __repr__(self) -> str:
        """Return string representation of ConfigDeployment."""
        device_count = self.inventory_loader.get_device_count()
        template_count = len(self.template_engine.list_templates())
        return (
            f"ConfigDeployment("
            f"devices={device_count}, "
            f"templates={template_count}, "
            f"auto_backup={self.auto_backup})"
        )


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage of the ConfigDeployment class.
    Run this script directly to test deployment functionality.
    """
    from .utils import setup_logging

    # Setup logging
    logger = setup_logging(log_level="INFO")

    try:
        print_separator("=", 80)
        print("Configuration Deployment System - Demo")
        print_separator("=", 80)
        print()

        # Initialize deployment manager
        print_info("Initializing deployment manager...")
        deployer = ConfigDeployment(auto_backup=True)
        print_success(f"Deployment manager initialized: {deployer}")
        print()

        # List available templates
        print_info("Available templates:")
        templates = deployer.template_engine.list_templates()
        for template in templates:
            print(f"   - {template}")
        print()

        # Get device for testing
        print_info("Loading device from inventory...")
        spine1 = deployer.inventory_loader.get_device_by_name("spine1")

        if not spine1:
            print_error("Device 'spine1' not found in inventory")
            sys.exit(1)

        print_success(f"Device loaded: {spine1['name']} ({spine1['ip']})")
        print()

        # Example 1: Preview deployment (dry-run)
        print_separator("-", 80)
        print("EXAMPLE 1: Preview Deployment (Dry-Run)")
        print_separator("-", 80)

        variables = {
            'ntp_server': '10.0.0.1',
            'timezone': 'UTC'
        }

        if 'example_ntp.j2' in templates:
            preview = deployer.preview_deployment(
                spine1,
                'example_ntp.j2',
                variables
            )
            print(preview)
        else:
            print_error("Template 'example_ntp.j2' not found")

        print()

        # Example 2: Dry-run deployment
        print_separator("-", 80)
        print("EXAMPLE 2: Dry-Run Deployment")
        print_separator("-", 80)

        if 'example_ntp.j2' in templates:
            print_info("Performing dry-run deployment...")
            result = deployer.deploy_to_device(
                device=spine1,
                template_name='example_ntp.j2',
                variables=variables,
                dry_run=True
            )

            if result['success']:
                print_success("Dry-run successful")
                print(f"Preview:\n{result['config_preview']}")
            else:
                print_error(f"Dry-run failed: {result['error']}")

        print()

        # Example 3: Deploy to multiple devices (dry-run)
        print_separator("-", 80)
        print("EXAMPLE 3: Multi-Device Deployment (Dry-Run)")
        print_separator("-", 80)

        devices = deployer.inventory_loader.get_devices_by_role("spine")

        if devices and 'example_ntp.j2' in templates:
            print_info(f"Deploying to {len(devices)} spine devices (dry-run)...")

            results = deployer.deploy_to_multiple_devices(
                devices=devices,
                template_name='example_ntp.j2',
                variables_list={'ntp_server': '10.0.0.1'},
                dry_run=True,
                parallel=False
            )

            # Generate and display report
            report = deployer.generate_deployment_report(results)
            print()
            print(report)

        print()
        print_separator("=", 80)
        print_success("Demo completed successfully!")
        print_separator("=", 80)

        print()
        print("NOTE: This was a dry-run demo. To actually deploy configurations,")
        print("set dry_run=False in the deploy methods.")

    except FileNotFoundError as e:
        print_error(f"File not found: {e}")
        print("\nMake sure you're running this script from the project root directory.")
        sys.exit(1)

    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
