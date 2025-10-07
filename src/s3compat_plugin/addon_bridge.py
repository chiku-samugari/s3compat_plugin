"""
Bridge module to make s3compat_plugin.addon discoverable as addons.s3compat

This module creates the 'addons' namespace and registers s3compat_plugin.addon
as 'addons.s3compat' to match OSF's addon discovery mechanism.

OSF's init_addons() function (website/app.py:44) uses Django's app registry
to load addons with the pattern: apps.get_app_config(f'addons_{addon_name}')

For 's3compat', this resolves to:
  1. INSTALLED_APPS entry: 's3compat_plugin.addon'
  2. App config label: 'addons_s3compat'
  3. Import path for backwards compatibility: 'addons.s3compat'
"""
import sys
from types import ModuleType

# Create the addons namespace package if it doesn't exist
if 'addons' not in sys.modules:
    addons = ModuleType('addons')
    addons.__path__ = []
    addons.__package__ = 'addons'
    addons.__file__ = __file__
    sys.modules['addons'] = addons
else:
    addons = sys.modules['addons']

# Import the actual addon module
from s3compat_plugin import addon as s3compat_module

# Register it as addons.s3compat for backwards compatibility
sys.modules['addons.s3compat'] = s3compat_module
setattr(addons, 's3compat', s3compat_module)

# Ensure the namespace has a path
if not hasattr(addons, '__path__'):
    addons.__path__ = []

__all__ = ['s3compat_module']
