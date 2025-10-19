from functools import partial
from django.db.models.options import make_immutable_fields_list
from typedmodels.models import TypedModel, TypedModelMetaclass


class TypedModelRejoinMixin:
    """
    Usage:
        class MyFileNode(BaseFileNode):
            _provider = 'myaddon'
            db_owner = 'osf'

            class Meta:
                proxy = True # Escape from TypedModel
                app_label = 'myaddon'   # Keeps migrations in our addon

        class MyFile(TypedModelRejoinMixin, MyFileNode, File):
            class Meta:
                proxy = True
                app_label = 'myaddon'
    """

    @classmethod
    def rejoin(cls):
        """
        Manually register the class `cls` in the TypedModel registry of
        its base class that directly inherits TypedModel. This method
        replicates what TypedModelMetaclass.__new__ does for subclasses
        that does not explicitly specified to be a proxy class.

        Should be called once per model, typically in the
        AppConfig.ready() method.
        """
        base_class = cls._find_typedmodel_base()

        if not base_class:
            raise ValueError(
                f"Cannot register {cls.__name__}: no suitable TypedModel base class found. "
                f"This mixin only works with subclasses of TypedModel."
            )

        if not hasattr(base_class, '_typedmodels_registry'):
            raise ValueError(
                f"Cannot register {cls.__name__}: base class {base_class.__name__} "
                f"does not have _typedmodels_registry. Is it a TypedModel?"
            )

        # Build the type identifier
        # f"{app_label}.{model_name} in the case of TypedModel, but we
        # use `cls.db_owner` field instead of `app_label` to keep the
        # model creation migrations into THIS app.
        opts = cls._meta
        model_name = opts.model_name
        typ = "%s.%s" % (cls.db_owner, model_name)

        # Check if already registered
        if typ in base_class._typedmodels_registry:
            existing_cls = base_class._typedmodels_registry[typ]
            if existing_cls is cls:
                # Already registered correctly
                return
            else:
                raise ValueError(
                    f"Type '{typ}' is already registered to {existing_cls.__name__}, "
                    f"cannot register to {cls.__name__}"
                )

        # Set the type attributes on this class
        cls._typedmodels_type = typ
        cls._typedmodels_subtypes = [typ]

        # Register in the base class registry
        base_class._typedmodels_registry[typ] = cls

        # Notify any intermediate proxy superclasses about this new
        # subtype. It allows queries on intermediate classes to include
        # this subclass.
        for superclass in cls.mro():
            if (
                issubclass(superclass, base_class)
                and superclass not in (cls, base_class)
                and hasattr(superclass, "_typedmodels_type")
            ):
                if typ not in superclass._typedmodels_subtypes:
                    superclass._typedmodels_subtypes.append(typ)

        # Set declared_fields if not already set
        # declared_fields should contain any Field instances declared on THIS class
        # For pure proxy models with no new fields, this will be empty
        if not hasattr(cls._meta, 'declared_fields'):
            cls._meta.declared_fields = {}

        # IMPORTANT: We deliberately DO NOT call
        # TypedModelMetaclass._patch_fields_cache here.
        #
        # `_patch_fields_cache` modifies `_get_fields` to filter fields
        # based on `_model_has_field`. This is needed when subclasses
        # add their own fields, to prevent those fields from appearing
        # on sibling classes.
        #
        # However, for external addon models that don't add new fields
        # (just inherit from File/Folder), the patching causes problems:
        # 1. It can incorrectly filter out base class fields like 'is_root'
        # 2. The _model_has_field logic doesn't account for multi-level
        #   proxy inheritance
        # 3. Since we're not adding fields, there's no risk of field leakage
        #
        # If some addon models DO add new fields, we may need to enable
        # this, but that will need to ensure `declared_fields` is
        # properly set with those field instances.
        #
        # TypedModelMetaclass._patch_fields_cache(cls, base_class)

        # Set base_class attribute if not already set
        if not hasattr(cls, 'base_class'):
            cls.base_class = base_class

    @classmethod
    def _find_typedmodel_base(cls):
        """
        Find the base TypedModel class in the MRO.

        This replicates the logic from TypedModelMetaclass.__new__ (lines 49-60)
        to find the non-proxy, non-abstract base class that is a subclass of TypedModel.

        Returns:
            The base TypedModel class, or None if not found.
        """
        mro = list(cls.__bases__)
        while mro:
            base_class = mro.pop(-1)
            if (
                isinstance(base_class, type)
                and issubclass(base_class, TypedModel)
                and base_class is not TypedModel
            ):
                if base_class._meta.proxy or base_class._meta.abstract:
                    # Continue up the MRO looking for non-proxy base classes
                    mro.extend(base_class.__bases__)
                else:
                    return base_class
        return None


def rejoin_models(*model_classes):
    """
    Convenience function to register multiple models at once.

    Usage in apps.py:
        from .models import MyFile, MyFolder
        from .typedmodel_workaround import register_all_models

        class MyAddonConfig(AppConfig):
            def ready(self):
                register_all_models(MyFile, MyFolder)

    Args:
        *model_classes: Model classes that use TypedModelRejoinMixin
    """
    for model_cls in model_classes:
        if not hasattr(model_cls, 'rejoin'):
            raise TypeError(
                f"{model_cls.__name__} does not have rejoin. "
                f"Did you forget to inherit from TypedModelRejoinMixin?"
            )
        model_cls.rejoin()
