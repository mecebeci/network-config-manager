"""Tests for template_engine module."""

import pytest
from src.template_engine import TemplateEngine


@pytest.mark.unit
class TestTemplateEngine:
    """Test cases for TemplateEngine class."""

    def test_render_template(self, temp_dir, test_template_file):
        """Test rendering template with variables."""
        engine = TemplateEngine(template_dir=temp_dir)
        variables = {
            'hostname': 'spine1',
            'timestamp': '2025-02-03 12:00:00',
            'ntp_server': '10.0.0.1'
        }
        result = engine.render_template('test_template.j2', variables)
        assert 'spine1' in result
        assert '10.0.0.1' in result

    def test_render_from_string(self):
        """Test rendering template from string."""
        engine = TemplateEngine()
        template_string = "Hello {{ name }}!"
        variables = {'name': 'World'}
        result = engine.render_from_string(template_string, variables)
        assert result.strip() == "Hello World!"

    def test_list_templates(self, temp_dir, test_template_file):
        """Test listing available templates."""
        engine = TemplateEngine(template_dir=temp_dir)
        templates = engine.list_templates()
        assert 'test_template.j2' in templates

    def test_validate_template(self, temp_dir, test_template_file):
        """Test template validation."""
        engine = TemplateEngine(template_dir=temp_dir)
        is_valid, message = engine.validate_template('test_template.j2')
        assert is_valid is True

    def test_template_not_found(self, temp_dir):
        """Test loading non-existent template."""
        engine = TemplateEngine(template_dir=temp_dir)
        with pytest.raises(Exception):
            engine.render_template('nonexistent.j2', {})

    def test_missing_variable(self, temp_dir, test_template_file):
        """Test rendering with missing variable."""
        engine = TemplateEngine(template_dir=temp_dir)
        variables = {
            'hostname': 'spine1',
            'timestamp': '2025-02-03 12:00:00'
            # missing ntp_server
        }
        # Should either handle gracefully or raise appropriate error
        result = engine.render_template('test_template.j2', variables)
        assert 'spine1' in result
