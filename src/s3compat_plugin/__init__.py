"""
s3compat_plugin - S3 Compatible Storage plugin for OSF/Gravyvalet

This package provides three integrated Django apps for S3-compatible storage integration:
- addon_imp: Foreign Addon Imp for Gravyvalet
- provider: WaterButler Provider for file operations
- addon: OSF.io Addon for user and project management
"""

from .__version__ import __version__

__all__ = ["__version__"]
