# `s3compat_plugin`

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![Django Version](https://img.shields.io/badge/django-4.2%2B-green)](https://www.djangoproject.com/)

S3 Compatible Storage plugin for OSF (Open Science Framework).

This package provides three integrated Django apps that enable S3-compatible storage integration:
- **Foreign Addon Imp** - gravyvalet integration for storage browsing and configuration
- **WaterButler Provider** - File operations provider for OSF's WaterButler
- **OSF Addon** - OSF.io addon for user and project storage management

## Features

- 🔌 Plug-and-play integration with OSF ecosystem
- 🌐 Support for any S3-compatible storage service (AWS S3, MinIO, Ceph, etc.)
- 🔐 Secure credential management with access key/secret key authentication
- 📁 Full file and folder browsing capabilities
- ⬆️⬇️ Upload and download operations via WaterButler
- 🎨 Customizable icons and UI elements

## Requirements

- Python 3.9 or higher
- Django 4.2 or higher
- boto3 (for S3 API communication)

## Installation

### Using pip

```bash
pip install s3compat_plugin
```

### Using poetry

```bash
poetry add s3compat_plugin
```

### From source (for development)

```bash
git clone https://github.com/chiku-samugari/s3compat_plugin.git
cd s3compat_plugin
pip install -e ".[dev]"
```

## Configuration

### osf.io

TBD

### gravyvalet

Add the apps to `INSTALLED_APPS`:

```python
# settings.py

INSTALLED_APPS = [
    # ... other apps
    "s3compat_plugin.addon_imp",
]
```

Register the addon in `ADDON_IMPS` configuration:

```python
# settings.py

ADDON_IMPS = {
    # ... other addons
    "S3COMPAT": 5000,  # Use a unique ID
}
```

### WaterButler

TBD

## Project Structure

```
s3compat_plugin/
├── src/
│   └── s3compat_plugin/
│       ├── addon_imp/        # Foreign Addon Imp for gravyvalet
│       ├── provider/         # WaterButler Provider
│       ├── addon/            # osf.io Addon
├── tests/                    # Test suite
├── docs/                     # Documentation
```


## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on top of the [Open Science Framework (OSF)](https://osf.io/)
- Uses [boto3](https://github.com/boto/boto3) for S3 API communication

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.

## Authors

- Takehiko Nawata - [GitHub](https://github.com/chiku-samugari)
