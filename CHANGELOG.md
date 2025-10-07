# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure with src layout
- Foreign Addon Imp for Gravyvalet integration
- WaterButler Provider for S3-compatible storage
- OSF.io Addon for user and project management
- Support for any S3-compatible storage service (AWS S3, MinIO, Ceph, etc.)
- Comprehensive test suite structure
- Documentation and examples

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [0.1.0] - 2025-10-07

### Added
- Initial release of s3compat_plugin
- Three integrated Django apps:
  - `s3compat_plugin.addon_imp`: Foreign Addon Imp for Gravyvalet
  - `s3compat_plugin.provider`: WaterButler Provider
  - `s3compat_plugin.addon`: OSF.io Addon
- boto3-based S3 API integration
- Credential validation and connection testing
- Storage browsing (buckets and objects)
- File upload/download operations via WaterButler
- Django models for OSF integration
- Static assets and templates for UI
- Apache 2.0 License

[Unreleased]: https://github.com/chiku-samugari/s3compat_plugin/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/chiku-samugari/s3compat_plugin/releases/tag/v0.1.0
