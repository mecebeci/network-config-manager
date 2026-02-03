import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import re

try:
    from jinja2 import (
        Environment,
        FileSystemLoader,
        Template,
        TemplateError,
        TemplateNotFound,
        TemplateSyntaxError,
        UndefinedError,
        meta
    )
except ImportError:
    print("Error: jinja2 module not found. Install it with: pip install jinja2")
    sys.exit(1)

from utils import get_logger, ensure_directory, safe_write_file, get_human_timestamp


# ============================================================================
# TEMPLATE ENGINE CLASS
# ============================================================================

class TemplateEngine:
    """
    Jinja2-based template engine for network configuration generation.

    This class handles loading, rendering, and validating Jinja2 templates
    for network device configuration generation. It provides a clean interface
    for working with templates and supports various operations including
    template listing, variable extraction, and syntax validation.

    Attributes:
        template_dir (str): Directory containing template files
        env (jinja2.Environment): Jinja2 environment instance
        logger (logging.Logger): Logger instance for this class

    Example:
        # Initialize with default template directory
        engine = TemplateEngine()

        # Or specify custom directory
        engine = TemplateEngine(template_dir="custom/templates")

        # Render a template
        config = engine.render_template('ntp.j2', {
            'hostname': 'router1',
            'ntp_server': '10.0.0.1'
        })
    """

    def __init__(self, template_dir: str = "configs/templates"):
        """
        Initialize the Template Engine.

        Sets up the Jinja2 environment with appropriate loaders and settings.
        Creates the template directory if it doesn't exist and initializes
        example templates if the directory is empty.

        Args:
            template_dir: Path to directory containing template files.
                         Defaults to "configs/templates"

        Example:
            engine = TemplateEngine()
            # or
            engine = TemplateEngine(template_dir="my/templates")
        """
        self.template_dir = template_dir
        self.logger = get_logger(__name__)

        # Create template directory if it doesn't exist
        if not os.path.exists(template_dir):
            self.logger.info(f"Creating template directory: {template_dir}")
            ensure_directory(template_dir)

        # Setup Jinja2 environment
        try:
            self.env = Environment(
                loader=FileSystemLoader(template_dir),
                trim_blocks=True,           # Remove first newline after block
                lstrip_blocks=True,         # Strip leading spaces/tabs from blocks
                keep_trailing_newline=True, # Preserve trailing newline in templates
                autoescape=False            # Don't escape HTML (we're generating configs)
            )
            self.logger.info(f"Template engine initialized with directory: {template_dir}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Jinja2 environment: {e}")
            raise

        # Create example templates if directory is empty
        if not self.list_templates():
            self.logger.info("Template directory is empty, creating example templates")
            create_example_templates(template_dir)

    def list_templates(self) -> List[str]:
        """
        List all available templates in the template directory.

        Scans the template directory for .j2 files and returns their names.
        Returns an empty list if the directory is empty or doesn't exist.

        Returns:
            List of template filenames (with .j2 extension)

        Example:
            engine = TemplateEngine()
            templates = engine.list_templates()
            # Returns: ['ntp_config.j2', 'snmp_config.j2', 'interface.j2']

            for template in templates:
                print(f"Available: {template}")
        """
        try:
            templates = []
            template_path = Path(self.template_dir)

            if not template_path.exists():
                self.logger.warning(f"Template directory does not exist: {self.template_dir}")
                return []

            # Find all .j2 files
            for file in template_path.iterdir():
                if file.is_file() and file.suffix == '.j2':
                    templates.append(file.name)

            templates.sort()  # Sort alphabetically
            self.logger.debug(f"Found {len(templates)} templates")
            return templates

        except Exception as e:
            self.logger.error(f"Error listing templates: {e}")
            return []

    def load_template(self, template_name: str) -> Template:
        """
        Load a template by name.

        Loads the specified template from the template directory.
        Automatically adds .j2 extension if not present.

        Args:
            template_name: Name of the template file (with or without .j2 extension)

        Returns:
            Jinja2 Template object

        Raises:
            TemplateNotFound: If the template file doesn't exist
            TemplateError: If there's an error loading the template

        Example:
            engine = TemplateEngine()
            template = engine.load_template('ntp_config.j2')
            # or
            template = engine.load_template('ntp_config')  # .j2 added automatically
        """
        # Add .j2 extension if not present
        if not template_name.endswith('.j2'):
            template_name = f"{template_name}.j2"

        try:
            self.logger.debug(f"Loading template: {template_name}")
            template = self.env.get_template(template_name)
            self.logger.info(f"Template loaded successfully: {template_name}")
            return template

        except TemplateNotFound:
            self.logger.error(f"Template not found: {template_name}")
            raise TemplateNotFound(f"Template '{template_name}' not found in {self.template_dir}")

        except TemplateError as e:
            self.logger.error(f"Error loading template {template_name}: {e}")
            raise

    def render_template(self, template_name: str, variables: Dict) -> str:
        """
        Load and render a template with the provided variables.

        This is the main method for generating configurations from templates.
        It loads the template and renders it with the provided variables.

        Args:
            template_name: Name of the template file (with or without .j2 extension)
            variables: Dictionary of variables to use in rendering.
                      Can include device data (hostname, ip, role), custom variables, etc.

        Returns:
            Rendered configuration as a string

        Raises:
            TemplateNotFound: If template doesn't exist
            TemplateError: If rendering fails
            UndefinedError: If a required variable is missing

        Example:
            engine = TemplateEngine()

            variables = {
                'hostname': 'spine1',
                'ntp_server': '10.0.0.1',
                'timezone': 'UTC',
                'timestamp': '2025-02-03 10:30:00'
            }

            config = engine.render_template('ntp_config.j2', variables)
            print(config)

            # Save to file
            with open('configs/spine1_ntp.cfg', 'w') as f:
                f.write(config)
        """
        try:
            # Load template
            template = self.load_template(template_name)

            # Add timestamp if not provided
            if 'timestamp' not in variables:
                variables['timestamp'] = get_human_timestamp()

            # Render template
            self.logger.debug(f"Rendering template '{template_name}' with {len(variables)} variables")
            rendered = template.render(**variables)

            self.logger.info(f"Template '{template_name}' rendered successfully")
            return rendered

        except UndefinedError as e:
            self.logger.error(f"Missing required variable in template '{template_name}': {e}")
            raise TemplateError(f"Missing required variable: {e}")

        except TemplateError as e:
            self.logger.error(f"Error rendering template '{template_name}': {e}")
            raise

    def render_from_string(self, template_string: str, variables: Dict) -> str:
        """
        Render a template from a string instead of a file.

        Useful for inline templates, testing, or dynamically generated templates.

        Args:
            template_string: Template content as a string
            variables: Dictionary of variables for rendering

        Returns:
            Rendered configuration as a string

        Raises:
            TemplateError: If rendering fails

        Example:
            engine = TemplateEngine()

            template_str = '''
            ! Configuration for {{ hostname }}
            /system ntp
                server {{ ntp_server }}
            '''

            variables = {
                'hostname': 'router1',
                'ntp_server': '10.0.0.1'
            }

            config = engine.render_from_string(template_str, variables)
            print(config)
        """
        try:
            # Add timestamp if not provided
            if 'timestamp' not in variables:
                variables['timestamp'] = get_human_timestamp()

            # Create template from string
            template = self.env.from_string(template_string)

            # Render
            self.logger.debug(f"Rendering template from string with {len(variables)} variables")
            rendered = template.render(**variables)

            self.logger.info("Template string rendered successfully")
            return rendered

        except TemplateError as e:
            self.logger.error(f"Error rendering template string: {e}")
            raise

    def validate_template(self, template_name: str) -> Tuple[bool, str]:
        """
        Validate template syntax without rendering.

        Checks if the template has valid Jinja2 syntax by attempting to parse it.
        This doesn't check if all required variables are present, only syntax.

        Args:
            template_name: Name of the template to validate

        Returns:
            Tuple of (is_valid, message):
                - (True, "Valid") if template syntax is correct
                - (False, error_message) if there are syntax errors

        Example:
            engine = TemplateEngine()

            is_valid, message = engine.validate_template('ntp_config.j2')
            if is_valid:
                print(f"✓ Template is valid: {message}")
            else:
                print(f"✗ Template has errors: {message}")
        """
        # Add .j2 extension if not present
        if not template_name.endswith('.j2'):
            template_name = f"{template_name}.j2"

        try:
            # Try to load and parse the template
            template = self.load_template(template_name)

            # If we got here, the template is syntactically valid
            self.logger.info(f"Template '{template_name}' validated successfully")
            return (True, "Valid")

        except TemplateSyntaxError as e:
            error_msg = f"Syntax error at line {e.lineno}: {e.message}"
            self.logger.warning(f"Template '{template_name}' validation failed: {error_msg}")
            return (False, error_msg)

        except TemplateNotFound:
            error_msg = f"Template not found: {template_name}"
            self.logger.warning(error_msg)
            return (False, error_msg)

        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            self.logger.error(f"Template '{template_name}' validation failed: {error_msg}")
            return (False, error_msg)

    def preview_template(self, template_name: str, variables: Dict) -> str:
        """
        Render template and return a formatted preview.

        Similar to render_template but adds a header indicating this is
        a preview. Used for dry-run operations before actual deployment.

        Args:
            template_name: Name of the template file
            variables: Dictionary of variables for rendering

        Returns:
            Rendered configuration with preview header

        Example:
            engine = TemplateEngine()

            variables = {
                'hostname': 'spine1',
                'ntp_server': '10.0.0.1'
            }

            preview = engine.preview_template('ntp_config.j2', variables)
            print(preview)
            # Output:
            # ========================================
            # PREVIEW MODE - Template: ntp_config.j2
            # Generated: 2025-02-03 10:30:00
            # ========================================
            # [rendered configuration here]
        """
        try:
            # Render the template
            rendered = self.render_template(template_name, variables)

            # Add preview header
            separator = "=" * 80
            timestamp = variables.get('timestamp', get_human_timestamp())

            preview = f"""{separator}
PREVIEW MODE - Template: {template_name}
Generated: {timestamp}
{separator}

{rendered}

{separator}
END PREVIEW
{separator}
"""

            self.logger.debug(f"Preview generated for template: {template_name}")
            return preview

        except Exception as e:
            self.logger.error(f"Error generating preview for '{template_name}': {e}")
            raise

    def get_template_variables(self, template_name: str) -> Set[str]:
        """
        Extract variable names used in a template.

        Parses the template and identifies all variable names referenced
        in {{ variable }} blocks. Useful for validation and documentation.

        Args:
            template_name: Name of the template to analyze

        Returns:
            Set of variable names found in the template

        Example:
            engine = TemplateEngine()

            variables = engine.get_template_variables('ntp_config.j2')
            print(f"Required variables: {variables}")
            # Output: {'hostname', 'ntp_server', 'timezone', 'timestamp'}

            # Check if all required variables are provided
            provided_vars = {'hostname': 'router1', 'ntp_server': '10.0.0.1'}
            missing = variables - set(provided_vars.keys())
            if missing:
                print(f"Missing variables: {missing}")
        """
        # Add .j2 extension if not present
        if not template_name.endswith('.j2'):
            template_name = f"{template_name}.j2"

        try:
            # Get template source
            template_path = Path(self.template_dir) / template_name

            if not template_path.exists():
                self.logger.error(f"Template not found: {template_name}")
                raise TemplateNotFound(f"Template '{template_name}' not found")

            with open(template_path, 'r', encoding='utf-8') as f:
                template_source = f.read()

            # Parse template and extract variables
            ast = self.env.parse(template_source)
            variables = meta.find_undeclared_variables(ast)

            self.logger.debug(f"Found {len(variables)} variables in template '{template_name}'")
            return variables

        except Exception as e:
            self.logger.error(f"Error extracting variables from '{template_name}': {e}")
            raise


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_example_templates(template_dir: str = "configs/templates") -> None:
    """
    Create example templates for common network configuration use cases.

    This function creates sample Jinja2 templates in the specified directory
    if they don't already exist. The templates demonstrate SR Linux configuration
    syntax and common configuration patterns.

    Templates created:
        - example_ntp.j2: NTP server configuration
        - example_snmp.j2: SNMP community configuration
        - example_interface.j2: Interface and subinterface configuration

    Args:
        template_dir: Directory where templates should be created

    Example:
        create_example_templates()
        # or
        create_example_templates("custom/templates")
    """
    logger = get_logger(__name__)

    # Ensure directory exists
    ensure_directory(template_dir)

    # Define example templates
    templates = {
        'example_ntp.j2': '''! NTP Configuration for {{ hostname }}
! Generated: {{ timestamp }}

/system ntp
    admin-state enable
    server {{ ntp_server }} {
        admin-state enable
        prefer true
    }
''',

        'example_snmp.j2': '''! SNMP Configuration for {{ hostname }}

/system snmp
    admin-state enable
    network-instance mgmt {
        admin-state enable
    }
    community {{ snmp_community }} {
        authorization ro
    }
''',

        'example_interface.j2': '''! Interface Configuration for {{ hostname }}

/interface {{ interface_name }}
    admin-state enable
    description "{{ description | default('Configured by automation') }}"
    subinterface {{ subinterface_id | default(0) }} {
        admin-state enable
        {% if ip_address %}
        ipv4 {
            address {{ ip_address }}/{{ netmask | default(24) }}
        }
        {% endif %}
    }
'''
    }

    # Create each template
    for template_name, content in templates.items():
        template_path = os.path.join(template_dir, template_name)

        if not os.path.exists(template_path):
            logger.info(f"Creating example template: {template_name}")
            success = safe_write_file(template_path, content)

            if success:
                logger.info(f"Created: {template_path}")
            else:
                logger.error(f"Failed to create: {template_path}")
        else:
            logger.debug(f"Template already exists: {template_name}")

    logger.info(f"Example templates setup complete in {template_dir}")


# ============================================================================
# MAIN / DEMO
# ============================================================================

if __name__ == "__main__":
    """
    Demo script showing template engine capabilities.
    """
    from utils import setup_logging, print_separator, print_success, print_error

    # Setup logging
    logger = setup_logging(log_level="INFO")

    print_separator("=", 80)
    print("Template Engine Demo")
    print_separator("=", 80)

    try:
        # Initialize engine
        print("\n1. Initializing Template Engine...")
        engine = TemplateEngine()
        print_success("Engine initialized")

        # List templates
        print("\n2. Available Templates:")
        templates = engine.list_templates()
        for template in templates:
            print(f"   - {template}")

        # Validate templates
        print("\n3. Validating Templates:")
        for template in templates:
            is_valid, message = engine.validate_template(template)
            if is_valid:
                print_success(f"{template}: {message}")
            else:
                print_error(f"{template}: {message}")

        # Get template variables
        if templates:
            print(f"\n4. Variables in '{templates[0]}':")
            variables = engine.get_template_variables(templates[0])
            for var in sorted(variables):
                print(f"   - {var}")

        # Render example template
        print("\n5. Rendering Example Template:")
        if 'example_ntp.j2' in templates:
            test_vars = {
                'hostname': 'spine1',
                'ntp_server': '10.0.0.1'
            }

            config = engine.render_template('example_ntp.j2', test_vars)
            print("\nRendered Configuration:")
            print_separator("-", 60)
            print(config)
            print_separator("-", 60)

        # Test preview mode
        print("\n6. Preview Mode:")
        if 'example_ntp.j2' in templates:
            preview = engine.preview_template('example_ntp.j2', test_vars)
            print(preview)

        # Test render from string
        print("\n7. Render from String:")
        inline_template = "hostname {{ name }}\nip address {{ ip }}"
        result = engine.render_from_string(inline_template, {
            'name': 'test-router',
            'ip': '192.168.1.1'
        })
        print(result)

        print("\n")
        print_separator("=", 80)
        print_success("Demo completed successfully!")
        print_separator("=", 80)

    except Exception as e:
        print_error(f"Demo failed: {e}")
        logger.exception("Demo error")
        sys.exit(1)
