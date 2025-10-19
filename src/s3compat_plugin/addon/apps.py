import os
from addons.base.apps import BaseAddonAppConfig, generic_root_folder
from .settings import MAX_UPLOAD_SIZE

s3compat_root_folder = generic_root_folder('s3compat')

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(
    HERE,
    'templates'
)

class S3CompatAddonAppConfig(BaseAddonAppConfig):

    default = True
    name = 's3compat_plugin.addon'
    label = 'addons_s3compat'
    full_name = 'S3 Compatible Storage'
    short_name = 's3compat'
    owners = ['user', 'node']
    configs = ['accounts', 'node']
    categories = ['storage']
    has_hgrid_files = True
    max_file_size = MAX_UPLOAD_SIZE
    node_settings_template = os.path.join(TEMPLATE_PATH, 's3compat_node_settings.mako')
    user_settings_template = os.path.join(TEMPLATE_PATH, 's3compat_user_settings.mako')

    def ready(self):
        super().ready()

        # Import here to avoid AppRegistryNotReady errors
        from .models import S3CompatFileNode, S3CompatFile, S3CompatFolder
        from .typedmodel_workaround import register_all_models

        # Register the file/folder models in the TypedModel registry.
        # We explicitly define our models to be proxy which make the
        # classes unmanaged by TypedModel, and explicit `app_label` to
        # keep migrations in our addon (not in osf.io). By this
        # registration, the classes are put under control of TypedModel
        # again.
        register_all_models(S3CompatFileNode, S3CompatFile, S3CompatFolder)

    @property
    def get_hgrid_data(self):
        return s3compat_root_folder

    BUCKET_LINKED = 's3compat_bucket_linked'
    BUCKET_UNLINKED = 's3compat_bucket_unlinked'
    FILE_ADDED = 's3compat_file_added'
    FILE_REMOVED = 's3compat_file_removed'
    FILE_UPDATED = 's3compat_file_updated'
    FOLDER_CREATED = 's3compat_folder_created'
    NODE_AUTHORIZED = 's3compat_node_authorized'
    NODE_DEAUTHORIZED = 's3compat_node_deauthorized'
    NODE_DEAUTHORIZED_NO_USER = 's3compat_node_deauthorized_no_user'

    actions = (BUCKET_LINKED,
        BUCKET_UNLINKED,
        FILE_ADDED,
        FILE_REMOVED,
        FILE_UPDATED,
        FOLDER_CREATED,
        NODE_AUTHORIZED,
        NODE_DEAUTHORIZED,
        NODE_DEAUTHORIZED_NO_USER)

    @property
    def routes(self):
        from . import routes
        return [routes.api_routes]

    @property
    def user_settings(self):
        return self.get_model('UserSettings')

    @property
    def node_settings(self):
        return self.get_model('NodeSettings')
