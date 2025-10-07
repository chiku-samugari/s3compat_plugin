from addon_toolkit.interfaces.foreign_addon_imp_config import ForeignAddonImpConfig

from .imp import S3CompatStorageImp


class S3CompatForeignAddonImpConfig(ForeignAddonImpConfig):
    name = "s3compat_plugin.addon_imp"
    verbose_name = "S3 Compatible Storage"
    default = True

    @property
    def imp(self):
        return S3CompatStorageImp

    @property
    def addon_imp_name(self):
        return "S3COMPAT"
