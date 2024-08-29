# -*- coding: utf-8 -*- #
# Copyright 2023 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tools for making the most of GcsApi metadata."""

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

import copy

from apitools.base.py import encoding
from apitools.base.py import encoding_helper
from googlecloudsdk.api_lib.storage import metadata_util
from googlecloudsdk.api_lib.storage import request_config_factory
from googlecloudsdk.api_lib.storage.gcs_json import metadata_field_converters
from googlecloudsdk.api_lib.util import apis
from googlecloudsdk.command_lib.storage import encryption_util
from googlecloudsdk.command_lib.storage import errors
from googlecloudsdk.command_lib.storage import gzip_util
from googlecloudsdk.command_lib.storage import storage_url
from googlecloudsdk.command_lib.storage import user_request_args_factory
from googlecloudsdk.command_lib.storage.resources import gcs_resource_reference
from googlecloudsdk.command_lib.storage.resources import resource_reference
from googlecloudsdk.core import properties


# Similar to CORS above, we need a sentinel value allowing us to specify
# when a default object ACL should be private (containing no entries).
# A defaultObjectAcl value of [] means don't modify the default object ACL.
# A value of [PRIVATE_DEFAULT_OBJ_ACL] means create an empty/private default
# object ACL.
PRIVATE_DEFAULT_OBJECT_ACL = apis.GetMessagesModule(
    'storage', 'v1').ObjectAccessControl(id='PRIVATE_DEFAULT_OBJ_ACL')

_NO_TRANSFORM = 'no-transform'


def _message_to_dict(message):
  """Converts message to dict. Returns None is message is None."""
  if message is not None:
    result = encoding.MessageToDict(message)
    # Explicit comparison is needed because we don't want to return None for
    # False values.
    if result == []:  # pylint: disable=g-explicit-bool-comparison
      return None
    return result
  return None


def copy_object_metadata(source_metadata,
                         destination_metadata,
                         request_config,
                         should_deep_copy=False):
  """Copies specific metadata from source_metadata to destination_metadata.

  The API manually generates metadata for destination objects most of the time,
  but there are some fields that may not be populated.

  Args:
    source_metadata (messages.Object): Metadata from source object.
    destination_metadata (messages.Object): Metadata for destination object.
    request_config (request_config_factory.RequestConfig): Holds context info
      about the copy operation.
    should_deep_copy (bool): Copy all metadata, removing fields the
      backend must generate and preserving destination address.

  Returns:
    New destination metadata with data copied from source (messages.Object).
  """
  if should_deep_copy:
    destination_bucket = destination_metadata.bucket
    destination_name = destination_metadata.name
    destination_metadata = copy.deepcopy(source_metadata)
    destination_metadata.bucket = destination_bucket
    destination_metadata.name = destination_name
    # Some fields should be regenerated by the backend to avoid errors.
    destination_metadata.generation = None
    destination_metadata.id = None
    # pylint:disable=g-explicit-bool-comparison,singleton-comparison
    if request_config.resource_args.preserve_acl == False:
      # pylint:enable=g-explicit-bool-comparison,singleton-comparison
      destination_metadata.acl = []
  else:
    if request_config.resource_args.preserve_acl:
      if not source_metadata.acl:
        raise errors.Error(
            'Attempting to preserve ACLs but found no source ACLs.'
        )
      destination_metadata.acl = copy.deepcopy(source_metadata.acl)
    destination_metadata.cacheControl = source_metadata.cacheControl
    destination_metadata.contentDisposition = source_metadata.contentDisposition
    destination_metadata.contentEncoding = source_metadata.contentEncoding
    destination_metadata.contentLanguage = source_metadata.contentLanguage
    destination_metadata.contentType = source_metadata.contentType
    destination_metadata.crc32c = source_metadata.crc32c
    destination_metadata.customTime = source_metadata.customTime
    destination_metadata.md5Hash = source_metadata.md5Hash
    destination_metadata.metadata = copy.deepcopy(source_metadata.metadata)

  return destination_metadata


def get_apitools_metadata_from_url(cloud_url):
  """Takes storage_url.CloudUrl and returns appropriate Apitools message."""
  messages = apis.GetMessagesModule('storage', 'v1')
  if cloud_url.is_bucket():
    return messages.Bucket(name=cloud_url.bucket_name)
  elif cloud_url.is_object():
    generation = int(cloud_url.generation) if cloud_url.generation else None
    return messages.Object(
        name=cloud_url.object_name,
        bucket=cloud_url.bucket_name,
        generation=generation)


def get_bucket_resource_from_metadata(metadata):
  """Helper method to generate a BucketResource instance from GCS metadata.

  Args:
    metadata (messages.Bucket): Extract resource properties from this.

  Returns:
    BucketResource with properties populated by metadata.
  """
  url = storage_url.CloudUrl(
      scheme=storage_url.ProviderPrefix.GCS, bucket_name=metadata.name)

  if metadata.autoclass and metadata.autoclass.enabled:
    autoclass_enabled_time = metadata.autoclass.toggleTime
  else:
    autoclass_enabled_time = None

  uniform_bucket_level_access = getattr(
      getattr(metadata.iamConfiguration, 'uniformBucketLevelAccess', None),
      'enabled', None)

  return gcs_resource_reference.GcsBucketResource(
      url,
      acl=_message_to_dict(metadata.acl),
      autoclass=_message_to_dict(metadata.autoclass),
      autoclass_enabled_time=autoclass_enabled_time,
      cors_config=_message_to_dict(metadata.cors),
      creation_time=metadata.timeCreated,
      custom_placement_config=_message_to_dict(metadata.customPlacementConfig),
      default_acl=_message_to_dict(metadata.defaultObjectAcl),
      default_event_based_hold=metadata.defaultEventBasedHold or None,
      default_kms_key=getattr(metadata.encryption, 'defaultKmsKeyName', None),
      default_storage_class=metadata.storageClass,
      etag=metadata.etag,
      labels=_message_to_dict(metadata.labels),
      lifecycle_config=_message_to_dict(metadata.lifecycle),
      location=metadata.location,
      location_type=metadata.locationType,
      logging_config=_message_to_dict(metadata.logging),
      metadata=metadata,
      metageneration=metadata.metageneration,
      per_object_retention=_message_to_dict(metadata.objectRetention),
      project_number=metadata.projectNumber,
      public_access_prevention=getattr(
          metadata.iamConfiguration, 'publicAccessPrevention', None
      ),
      requester_pays=getattr(metadata.billing, 'requesterPays', None),
      retention_policy=_message_to_dict(metadata.retentionPolicy),
      rpo=metadata.rpo,
      satisfies_pzs=metadata.satisfiesPZS,
      soft_delete_policy=_message_to_dict(metadata.softDeletePolicy),
      uniform_bucket_level_access=uniform_bucket_level_access,
      update_time=metadata.updated,
      versioning_enabled=getattr(metadata.versioning, 'enabled', None),
      website_config=_message_to_dict(metadata.website),
  )


def get_metadata_from_bucket_resource(resource):
  """Helper method to generate Apitools metadata instance from BucketResource.

  Args:
    resource (BucketResource): Extract metadata properties from this.

  Returns:
    messages.Bucket with properties populated by resource.
  """
  messages = apis.GetMessagesModule('storage', 'v1')
  metadata = messages.Bucket(
      name=resource.name,
      etag=resource.etag,
      location=resource.location,
      storageClass=resource.default_storage_class)

  if resource.retention_period:
    metadata.retentionPolicy = messages.Bucket.RetentionPolicyValue(
        retentionPeriod=resource.retention_period)
  if resource.uniform_bucket_level_access:
    metadata.iamConfiguration = messages.Bucket.IamConfigurationValue(
        uniformBucketLevelAccess=messages.Bucket.IamConfigurationValue
        .UniformBucketLevelAccessValue(
            enabled=resource.uniform_bucket_level_access))

  return metadata


def get_anywhere_cache_resource_from_metadata(metadata):
  url = storage_url.CloudUrl(
      scheme=storage_url.ProviderPrefix.GCS,
      bucket_name=metadata.bucket,
      object_name=metadata.anywhereCacheId,
  )
  return gcs_resource_reference.GcsAnywhereCacheResource(
      admission_policy=metadata.admissionPolicy,
      anywhere_cache_id=metadata.anywhereCacheId,
      bucket=metadata.bucket,
      create_time=metadata.createTime,
      id_string=metadata.id,
      kind=metadata.kind,
      metadata=metadata,
      pending_update=metadata.pendingUpdate,
      state=metadata.state,
      storage_url=url,
      ttl=metadata.ttl,
      update_time=metadata.updateTime,
      zone=metadata.zone,
  )


def get_object_resource_from_metadata(metadata):
  """Helper method to generate a ObjectResource instance from GCS metadata.

  Args:
    metadata (messages.Object): Extract resource properties from this.

  Returns:
    ObjectResource with properties populated by metadata.
  """
  if metadata.generation is not None:
    # Generation may be 0 integer, which is valid although falsy.
    generation = str(metadata.generation)
  else:
    generation = None
  url = storage_url.CloudUrl(
      scheme=storage_url.ProviderPrefix.GCS,
      bucket_name=metadata.bucket,
      object_name=metadata.name,
      generation=generation)

  if metadata.customerEncryption:
    decryption_key_hash_sha256 = metadata.customerEncryption.keySha256
    encryption_algorithm = metadata.customerEncryption.encryptionAlgorithm
  else:
    decryption_key_hash_sha256 = encryption_algorithm = None

  return gcs_resource_reference.GcsObjectResource(
      url,
      acl=_message_to_dict(metadata.acl),
      cache_control=metadata.cacheControl,
      component_count=metadata.componentCount,
      content_disposition=metadata.contentDisposition,
      content_encoding=metadata.contentEncoding,
      content_language=metadata.contentLanguage,
      content_type=metadata.contentType,
      crc32c_hash=metadata.crc32c,
      creation_time=metadata.timeCreated,
      custom_fields=_message_to_dict(metadata.metadata),
      custom_time=metadata.customTime,
      decryption_key_hash_sha256=decryption_key_hash_sha256,
      encryption_algorithm=encryption_algorithm,
      etag=metadata.etag,
      event_based_hold=(
          metadata.eventBasedHold if metadata.eventBasedHold else None
      ),
      hard_delete_time=metadata.hardDeleteTime,
      kms_key=metadata.kmsKeyName,
      md5_hash=metadata.md5Hash,
      metadata=metadata,
      metageneration=metadata.metageneration,
      noncurrent_time=metadata.timeDeleted,
      retention_expiration=metadata.retentionExpirationTime,
      retention_settings=_message_to_dict(metadata.retention),
      size=metadata.size,
      soft_delete_time=metadata.softDeleteTime,
      storage_class=metadata.storageClass,
      storage_class_update_time=metadata.timeStorageClassUpdated,
      temporary_hold=metadata.temporaryHold if metadata.temporaryHold else None,
      update_time=metadata.updated,
  )


def _get_matching_grant_identifier_to_remove_for_shim(
    existing_grant, grant_identifiers
):
  """Shim-only support for case-insensitive matching on non-entity metadata.

  Ports the logic here:
  https://github.com/GoogleCloudPlatform/gsutil/blob/0d9d0175b2b10430471c7b744646e56210f991d3/gslib/utils/acl_helper.py#L291

  Args:
    existing_grant (BucketAccessControl|ObjectAccessControl): A grant currently
      in a resource's access control list.
    grant_identifiers (Iterable[str]): User input specifying the grants to
      remove.

  Returns:
    A string matching existing_grant in grant_identifiers if one exists.
      Otherwise, None. Note that this involves preserving the original case of
      the identifier, despite the fact that this function performs a
      case-insensitive comparison.
  """
  # Making this mapping here is inefficient (O(n^2)), but it allows us to
  # compartmentalize shim logic. I/O time is likely our main bottleneck anyway.
  normalized_identifier_to_original = {
      identifier.lower(): identifier for identifier in grant_identifiers
  }

  if existing_grant.entityId:
    normalized_entity_id = existing_grant.entityId.lower()
    if normalized_entity_id in normalized_identifier_to_original:
      return normalized_identifier_to_original[normalized_entity_id]

  if existing_grant.email:
    normalized_email = existing_grant.email.lower()
    if normalized_email in normalized_identifier_to_original:
      return normalized_identifier_to_original[normalized_email]

  if existing_grant.domain:
    normalized_domain = existing_grant.domain.lower()
    if normalized_domain in normalized_identifier_to_original:
      return normalized_identifier_to_original[normalized_domain]

  if existing_grant.projectTeam:
    normalized_identifier = (
        '{}-{}'.format(
            existing_grant.projectTeam.team,
            existing_grant.projectTeam.projectNumber,
        )
    ).lower()
    if normalized_identifier in normalized_identifier_to_original:
      return normalized_identifier_to_original[normalized_identifier]

  if existing_grant.entity:
    normalized_entity = existing_grant.entity.lower()
    if (
        normalized_entity in normalized_identifier_to_original
        and normalized_entity in ['allusers', 'allauthenticatedusers']
    ):
      return normalized_identifier_to_original[normalized_entity]


def _get_list_with_added_and_removed_acl_grants(
    acl_list, resource_args, is_bucket=False, is_default_object_acl=False
):
  """Returns shallow copy of ACL policy object with requested changes.

  Args:
    acl_list (list): Contains Apitools ACL objects for buckets or objects.
    resource_args (request_config_factory._ResourceConfig): Contains desired
      changes for the ACL policy.
    is_bucket (bool): Used to determine if ACL for bucket or object. False
      implies a cloud storage object.
    is_default_object_acl (bool): Used to determine if target is default object
      ACL list.

  Returns:
    list: Shallow copy of acl_list with added and removed grants.
  """
  new_acl_list = []
  if is_default_object_acl:
    acl_identifiers_to_remove = set(
        resource_args.default_object_acl_grants_to_remove or []
    )
    acl_grants_to_add = resource_args.default_object_acl_grants_to_add or []
  else:
    acl_identifiers_to_remove = set(resource_args.acl_grants_to_remove or [])
    acl_grants_to_add = resource_args.acl_grants_to_add or []

  acl_identifiers_to_add = set(grant['entity'] for grant in acl_grants_to_add)

  found_match = {identifier: False for identifier in acl_identifiers_to_remove}
  for existing_grant in acl_list:
    if properties.VALUES.storage.run_by_gsutil_shim.GetBool():
      matched_identifier = _get_matching_grant_identifier_to_remove_for_shim(
          existing_grant, acl_identifiers_to_remove
      )
    elif existing_grant.entity in acl_identifiers_to_remove:
      matched_identifier = existing_grant.entity
    else:
      matched_identifier = None

    if matched_identifier in found_match:  # Grant should be removed.
      found_match[matched_identifier] = True

    # Gsutil's equivalent of this check involves checking more metadata fields:
    # https://github.com/GoogleCloudPlatform/gsutil/blob/0d9d0175b2b10430471c7b744646e56210f991d3/gslib/utils/acl_helper.py#L158
    # The shim handles creating entity strings and the case-insensitivity of
    # comparisons with the "all(Authenticated)Users" groups.
    elif existing_grant.entity not in acl_identifiers_to_add:
      # Grant is not being updated, so we add it as-is to new ACLs.
      new_acl_list.append(existing_grant)

  unmatched_entities = [k for k, v in found_match.items() if not v]
  if unmatched_entities:
    raise errors.Error(
        'ACL entities marked for removal did not match existing grants:'
        ' {}'.format(sorted(unmatched_entities))
    )

  acl_class = metadata_field_converters.get_bucket_or_object_acl_class(
      is_bucket)

  for new_grant in acl_grants_to_add:
    new_acl_list.append(
        acl_class(entity=new_grant.get('entity'), role=new_grant.get('role'))
    )

  return new_acl_list


def _get_labels_object_with_added_and_removed_labels(labels_object,
                                                     resource_args):
  """Returns shallow copy of bucket labels object with requested changes.

  Args:
    labels_object (messages.Bucket.LabelsValue|None): Existing labels.
    resource_args (request_config_factory._BucketConfig): Contains desired
      changes for labels list.

  Returns:
    messages.Bucket.LabelsValue|None: Contains shallow copy of labels list with
      added and removed values or None if there was no original object.
  """
  messages = apis.GetMessagesModule('storage', 'v1')
  if labels_object:
    existing_labels = labels_object.additionalProperties
  else:
    existing_labels = []
  new_labels = []

  labels_to_remove = set(resource_args.labels_to_remove or [])
  for existing_label in existing_labels:
    if existing_label.key in labels_to_remove:
      # The backend deletes labels whose value is None.
      new_labels.append(
          messages.Bucket.LabelsValue.AdditionalProperty(
              key=existing_label.key, value=None))
    else:
      new_labels.append(existing_label)

  labels_to_append = resource_args.labels_to_append or {}
  for key, value in labels_to_append.items():
    new_labels.append(
        messages.Bucket.LabelsValue.AdditionalProperty(key=key, value=value))

  if not (labels_object or new_labels):
    # Don't send extra data to the API if we're not adding or removing anything.
    return None
  # If all label objects have a None value, backend removes the whole property.
  return messages.Bucket.LabelsValue(additionalProperties=new_labels)


def update_bucket_metadata_from_request_config(bucket_metadata, request_config):
  """Sets Apitools Bucket fields based on values in request_config."""
  resource_args = getattr(request_config, 'resource_args', None)
  if not resource_args:
    return

  if (
      resource_args.enable_autoclass is not None
      or resource_args.autoclass_terminal_storage_class is not None
  ):
    bucket_metadata.autoclass = metadata_field_converters.process_autoclass(
        resource_args.enable_autoclass,
        resource_args.autoclass_terminal_storage_class,
    )
  if resource_args.enable_hierarchical_namespace is not None:
    bucket_metadata.hierarchicalNamespace = (
        metadata_field_converters.process_hierarchical_namespace(
            resource_args.enable_hierarchical_namespace
        )
    )
  if resource_args.cors_file_path is not None:
    bucket_metadata.cors = metadata_field_converters.process_cors(
        resource_args.cors_file_path)
  if resource_args.default_encryption_key is not None:
    bucket_metadata.encryption = (
        metadata_field_converters.process_default_encryption_key(
            resource_args.default_encryption_key))
  if resource_args.default_event_based_hold is not None:
    bucket_metadata.defaultEventBasedHold = (
        resource_args.default_event_based_hold)
  if resource_args.default_storage_class is not None:
    bucket_metadata.storageClass = (
        metadata_field_converters.process_default_storage_class(
            resource_args.default_storage_class))
  if resource_args.lifecycle_file_path is not None:
    bucket_metadata.lifecycle = (
        metadata_field_converters.process_lifecycle(
            resource_args.lifecycle_file_path))
  if resource_args.location is not None:
    bucket_metadata.location = resource_args.location
  if (resource_args.log_bucket is not None or
      resource_args.log_object_prefix is not None):
    bucket_metadata.logging = metadata_field_converters.process_log_config(
        bucket_metadata.name, resource_args.log_bucket,
        resource_args.log_object_prefix)
  if resource_args.placement is not None:
    bucket_metadata.customPlacementConfig = (
        metadata_field_converters.process_placement_config(
            resource_args.placement))
  if (resource_args.public_access_prevention is not None or
      resource_args.uniform_bucket_level_access is not None):
    # Note: The IAM policy (with role grants) is stored separately because it
    # has its own API.
    bucket_metadata.iamConfiguration = (
        metadata_field_converters.process_bucket_iam_configuration(
            bucket_metadata.iamConfiguration,
            resource_args.public_access_prevention,
            resource_args.uniform_bucket_level_access))
  if resource_args.recovery_point_objective is not None:
    bucket_metadata.rpo = resource_args.recovery_point_objective
  if resource_args.requester_pays is not None:
    bucket_metadata.billing = (
        metadata_field_converters.process_requester_pays(
            bucket_metadata.billing, resource_args.requester_pays))
  if resource_args.retention_period is not None:
    bucket_metadata.retentionPolicy = (
        metadata_field_converters.process_retention_period(
            resource_args.retention_period))
  if resource_args.soft_delete_duration is not None:
    bucket_metadata.softDeletePolicy = (
        metadata_field_converters.process_soft_delete_duration(
            resource_args.soft_delete_duration
        )
    )
  if resource_args.versioning is not None:
    bucket_metadata.versioning = (
        metadata_field_converters.process_versioning(
            resource_args.versioning))
  if (resource_args.web_error_page is not None or
      resource_args.web_main_page_suffix is not None):
    bucket_metadata.website = metadata_field_converters.process_website(
        resource_args.web_error_page, resource_args.web_main_page_suffix)

  if resource_args.acl_file_path is not None:
    bucket_metadata.acl = metadata_field_converters.process_acl_file(
        resource_args.acl_file_path, is_bucket=True
    )
  bucket_metadata.acl = (
      _get_list_with_added_and_removed_acl_grants(
          bucket_metadata.acl,
          resource_args,
          is_bucket=True,
          is_default_object_acl=False))

  if resource_args.default_object_acl_file_path is not None:
    bucket_metadata.defaultObjectAcl = (
        metadata_field_converters.process_acl_file(
            resource_args.default_object_acl_file_path, is_bucket=False
        )
    )
  bucket_metadata.defaultObjectAcl = (
      _get_list_with_added_and_removed_acl_grants(
          bucket_metadata.defaultObjectAcl,
          resource_args,
          is_bucket=False,
          is_default_object_acl=True))

  if resource_args.labels_file_path is not None:
    bucket_metadata.labels = metadata_field_converters.process_labels(
        bucket_metadata.labels, resource_args.labels_file_path)
  # Can still add labels after clear.
  bucket_metadata.labels = _get_labels_object_with_added_and_removed_labels(
      bucket_metadata.labels, resource_args)


def get_cleared_bucket_fields(request_config):
  """Gets a list of fields to be included in requests despite null values."""
  cleared_fields = []
  resource_args = getattr(request_config, 'resource_args', None)
  if not resource_args:
    return cleared_fields

  if (
      resource_args.cors_file_path == user_request_args_factory.CLEAR
      or resource_args.cors_file_path
      and not metadata_util.cached_read_yaml_json_file(
          resource_args.cors_file_path
      )
  ):
    # Empty JSON object similar to CLEAR flag.
    cleared_fields.append('cors')

  if resource_args.default_encryption_key == user_request_args_factory.CLEAR:
    cleared_fields.append('encryption')

  if resource_args.default_storage_class == user_request_args_factory.CLEAR:
    cleared_fields.append('storageClass')

  if resource_args.labels_file_path == user_request_args_factory.CLEAR:
    cleared_fields.append('labels')

  if (
      resource_args.lifecycle_file_path == user_request_args_factory.CLEAR
      or resource_args.lifecycle_file_path
      and not metadata_util.cached_read_yaml_json_file(
          resource_args.lifecycle_file_path
      )
  ):
    # Empty JSON object similar to CLEAR flag.
    cleared_fields.append('lifecycle')

  if resource_args.log_bucket == user_request_args_factory.CLEAR:
    cleared_fields.append('logging')
  elif resource_args.log_object_prefix == user_request_args_factory.CLEAR:
    cleared_fields.append('logging.logObjectPrefix')

  if resource_args.public_access_prevention == user_request_args_factory.CLEAR:
    cleared_fields.append('iamConfiguration.publicAccessPrevention')

  if resource_args.retention_period == user_request_args_factory.CLEAR:
    cleared_fields.append('retentionPolicy')

  if (
      resource_args.web_error_page
      == resource_args.web_main_page_suffix
      == user_request_args_factory.CLEAR
  ):
    cleared_fields.append('website')
  elif resource_args.web_error_page == user_request_args_factory.CLEAR:
    cleared_fields.append('website.notFoundPage')
  elif resource_args.web_main_page_suffix == user_request_args_factory.CLEAR:
    cleared_fields.append('website.mainPageSuffix')

  return cleared_fields


def get_cache_control(should_gzip_locally, resource_args):
  """Returns cache control metadata value.

  If should_gzip_locally is True, append 'no-transform' to cache control value
  with the user's given value.

  Args:
    should_gzip_locally (bool): True if file should be gzip locally.
    resource_args (request_config_factory._ObjectConfig): Holds settings for a
      cloud resource.

  Returns:
    (str|None) Cache control value.
  """
  if isinstance(resource_args, request_config_factory._ObjectConfig):  # pylint: disable=protected-access
    user_cache_control = resource_args.cache_control
  else:
    user_cache_control = None

  if should_gzip_locally:
    return (
        _NO_TRANSFORM
        if user_cache_control is None
        else '{}, {}'.format(user_cache_control, _NO_TRANSFORM)
    )

  return user_cache_control


def get_content_encoding(should_gzip_locally, resource_args):
  """Returns content encoding metadata value.

  If should_gzip_locally is True, return gzip.

  Args:
    should_gzip_locally (bool): True if file should be gzip locally.
    resource_args (request_config_factory._ObjectConfig): Holds settings for a
      cloud resource.

  Returns:
    (str|None) Content encoding value.
  """
  if should_gzip_locally:
    return 'gzip'

  if isinstance(resource_args, request_config_factory._ObjectConfig):  # pylint: disable=protected-access
    return resource_args.content_encoding

  return None


def get_should_gzip_locally(attributes_resource, request_config):
  if isinstance(attributes_resource, resource_reference.FileObjectResource):
    return gzip_util.should_gzip_locally(
        request_config.gzip_settings,
        attributes_resource.storage_url.object_name,
    )

  return False


def process_value_or_clear_flag(metadata, key, value):
  """Sets appropriate metadata based on value."""
  if value == user_request_args_factory.CLEAR:
    setattr(metadata, key, None)
  elif value is not None:
    setattr(metadata, key, value)


def update_object_metadata_from_request_config(
    object_metadata,
    request_config,
    attributes_resource=None,
    posix_to_set=None,
):
  """Sets Apitools Object fields based on values in request_config.

  User custom metadata takes precedence over preserved POSIX data.
  Gzip metadata changes take precedence over user custom metadata.

  Args:
    object_metadata (storage_v1_messages.Object): Existing object metadata.
    request_config (request_config): May contain data to add to object_metadata.
    attributes_resource (Resource|None): If present, used for parsing POSIX and
      symlink data from a resource for the --preserve-posix and/or
      --preserve_symlink flags. This value is ignored unless it is an instance
      of FileObjectResource.
    posix_to_set (PosixAttributes|None): Set as custom metadata on target.
  """
  resource_args = request_config.resource_args

  # Custom metadata & POSIX handling.
  if not object_metadata.metadata:
    existing_metadata = {}
  else:
    existing_metadata = encoding_helper.MessageToDict(
        object_metadata.metadata)

  custom_fields_dict = metadata_util.get_updated_custom_fields(
      existing_metadata,
      request_config,
      attributes_resource=attributes_resource,
      known_posix=posix_to_set,
  )
  if custom_fields_dict is not None:
    messages = apis.GetMessagesModule('storage', 'v1')
    object_metadata.metadata = encoding_helper.DictToMessage(
        custom_fields_dict, messages.Object.MetadataValue)

  should_gzip_locally = get_should_gzip_locally(
      attributes_resource, request_config)

  cache_control = get_cache_control(should_gzip_locally, resource_args)
  process_value_or_clear_flag(object_metadata, 'cacheControl', cache_control)

  content_encoding = get_content_encoding(should_gzip_locally, resource_args)
  process_value_or_clear_flag(object_metadata, 'contentEncoding',
                              content_encoding)

  if not resource_args:
    return

  # Encryption handling.
  if resource_args.encryption_key:
    if (resource_args.encryption_key == user_request_args_factory.CLEAR or
        resource_args.encryption_key.type is encryption_util.KeyType.CSEK):
      object_metadata.kmsKeyName = None
      # For CSEK, set the encryption in API request headers instead.
      object_metadata.customerEncryption = None
    elif resource_args.encryption_key.type is encryption_util.KeyType.CMEK:
      object_metadata.kmsKeyName = resource_args.encryption_key.key

  # General metadata handling.
  process_value_or_clear_flag(
      object_metadata, 'contentDisposition', resource_args.content_disposition
  )
  process_value_or_clear_flag(
      object_metadata, 'contentLanguage', resource_args.content_language
  )
  process_value_or_clear_flag(
      object_metadata, 'customTime', resource_args.custom_time
  )
  process_value_or_clear_flag(
      object_metadata, 'contentType', resource_args.content_type
  )
  process_value_or_clear_flag(
      object_metadata, 'md5Hash', resource_args.md5_hash
  )
  process_value_or_clear_flag(
      object_metadata, 'storageClass', resource_args.storage_class
  )

  if resource_args.acl_file_path is not None:
    object_metadata.acl = metadata_field_converters.process_acl_file(
        resource_args.acl_file_path
    )
  object_metadata.acl = _get_list_with_added_and_removed_acl_grants(
      object_metadata.acl, resource_args, is_bucket=False
  )

  if resource_args.event_based_hold is not None:
    object_metadata.eventBasedHold = resource_args.event_based_hold
  if resource_args.temporary_hold is not None:
    object_metadata.temporaryHold = resource_args.temporary_hold

  object_metadata.retention = (
      metadata_field_converters.process_object_retention(
          object_metadata.retention,
          resource_args.retain_until,
          resource_args.retention_mode,
      )
  )


def get_cleared_object_fields(request_config):
  """Gets a list of fields to be included in requests despite null values."""
  cleared_fields = []
  resource_args = request_config.resource_args
  if not resource_args:
    return cleared_fields

  if resource_args.cache_control == user_request_args_factory.CLEAR:
    cleared_fields.append('cacheControl')

  if resource_args.content_type == user_request_args_factory.CLEAR:
    cleared_fields.append('contentType')

  if resource_args.content_disposition == user_request_args_factory.CLEAR:
    cleared_fields.append('contentDisposition')

  if resource_args.content_encoding == user_request_args_factory.CLEAR:
    cleared_fields.append('contentEncoding')

  if resource_args.content_language == user_request_args_factory.CLEAR:
    cleared_fields.append('contentLanguage')

  if resource_args.custom_time == user_request_args_factory.CLEAR:
    cleared_fields.append('customTime')

  if (
      resource_args.retain_until == user_request_args_factory.CLEAR
      or resource_args.retention_mode == user_request_args_factory.CLEAR
  ):
    cleared_fields.append('retention')

  return cleared_fields


def get_managed_folder_resource_from_metadata(metadata):
  """Returns a ManagedFolderResource from Apitools metadata."""
  url = storage_url.CloudUrl(
      scheme=storage_url.ProviderPrefix.GCS,
      bucket_name=metadata.bucket,
      object_name=metadata.name,
  )
  return resource_reference.ManagedFolderResource(
      url,
      create_time=metadata.createTime,
      metadata=metadata,
      metageneration=metadata.metageneration,
      update_time=metadata.updateTime,
  )


def get_folder_resource_from_metadata(metadata):
  """Returns a FolderResource from Apitools metadata."""
  url = storage_url.CloudUrl(
      scheme=storage_url.ProviderPrefix.GCS,
      bucket_name=metadata.bucket,
      object_name=metadata.name,
  )
  return resource_reference.FolderResource(
      url,
      create_time=metadata.createTime,
      metadata=metadata,
      metageneration=metadata.metageneration,
      update_time=metadata.updateTime,
  )
