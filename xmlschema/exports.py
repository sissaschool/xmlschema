#
# Copyright (c), 2016-2023, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
import re
import pathlib
import logging
from itertools import chain
from typing import TYPE_CHECKING, Any, Optional, List
from urllib.parse import unquote, urlsplit

from .exceptions import XMLSchemaValueError
from .locations import LocationPath, is_remote_url
from .translation import gettext as _

if TYPE_CHECKING:
    from .validators import XMLSchemaBase

logger = logging.getLogger('xmlschema')

FIND_PATTERN = r'\bschemaLocation\s*=\s*[\'"]([^\'"]*)[\'"]'
REPLACE_PATTERN = r'\bschemaLocation\s*=\s*[\'"]\s*{0}\s*[\'"]'


def replace_location(text: str, location: str, repl_location: str) -> str:
    repl = 'schemaLocation="{}"'.format(repl_location)
    pattern = REPLACE_PATTERN.format(re.escape(location))
    return re.sub(pattern, repl, text)


def export_schema(obj: 'XMLSchemaBase', target_dir: str,
                  save_remote: bool = False,
                  remove_residuals: bool = True,
                  exclude_locations: Optional[List[str]] = None) -> None:

    def residuals_filter(x: str) -> bool:
        return is_remote_url(x) and x not in schema.includes and \
            (exclude_locations is None or x not in exclude_locations)

    target_path = pathlib.Path(target_dir)
    if target_path.is_dir():
        if list(target_path.iterdir()):
            msg = _("target directory {} is not empty")
            raise XMLSchemaValueError(msg.format(target_dir))
    elif target_path.exists():
        msg = _("target {} is not a directory")
        raise XMLSchemaValueError(msg.format(target_path.parent))
    elif not target_path.parent.exists():
        msg = _("target parent directory {} does not exist")
        raise XMLSchemaValueError(msg.format(target_path.parent))
    elif not target_path.parent.is_dir():
        msg = _("target parent {} is not a directory")
        raise XMLSchemaValueError(msg.format(target_path.parent))

    name = obj.name or 'schema.xsd'
    exports: Any = {obj: [LocationPath(unquote(name)), obj.get_text(), False]}
    path: Any
    modified_schemas: Any = set()

    if exclude_locations is None:
        exclude_locations = []

    logger.debug("Start export of schema %r", name)

    while True:
        current_length = len(exports)

        for schema in list(exports):
            if exports[schema][2]:
                continue  # Skip already processed schemas
            exports[schema][2] = True

            logger.debug("Process schema instance %r", schema)

            dir_path = exports[schema][0].parent
            imports_items = [(x.url, x) for x in schema.imports.values()
                             if x is not None and x.meta_schema is not None]

            schema_locations = set(
                x.strip() for x in re.findall(FIND_PATTERN, exports[schema][1])
            )

            for location, ref_schema in chain(schema.includes.items(), imports_items):
                if location in exclude_locations:
                    logger.debug("Location %r is excluded by argument", location)
                    continue

                # Find matching schema location
                if location in schema_locations:
                    schema_locations.remove(location)
                else:
                    name = ref_schema.name
                    assert isinstance(name, str)

                    matching_items = [x for x in schema_locations if x.endswith(name)]
                    if len(matching_items) == 1:
                        location = matching_items[0]
                        schema_locations.remove(location)
                    elif not matching_items:
                        logger.debug("Unmatched location %r, skip ...", location)
                        continue
                    else:
                        for item in matching_items:
                            item_path = LocationPath.from_uri(item)
                            if location.endswith(str(item_path).lstrip('.')):
                                location = item
                                schema_locations.remove(location)
                                break
                        else:
                            location = matching_items[0]
                            schema_locations.remove(location)

                    logger.debug("Matched location %r", location)

                if is_remote_url(location):
                    if not save_remote:
                        continue

                    parts = urlsplit(unquote(location))
                    path = LocationPath(parts.scheme). \
                        joinpath(parts.netloc). \
                        joinpath(parts.path.lstrip('/'))
                else:
                    if location.startswith('file:/'):
                        path = LocationPath(unquote(urlsplit(location).path))
                    else:
                        path = LocationPath(unquote(location))

                    if not path.is_absolute():
                        path = dir_path.joinpath(path).normalize()
                        if not str(path).startswith('..'):
                            # A relative path that doesn't exceed the loading schema dir
                            if ref_schema not in exports:
                                exports[ref_schema] = [path, ref_schema.get_text(), False]
                            continue

                        # Use the absolute schema path
                        schema_path = ref_schema.filepath
                        assert schema_path is not None
                        path = LocationPath(schema_path)

                    if path.drive:
                        drive = path.drive.split(':')[0]
                        path = LocationPath(drive).joinpath('/'.join(path.parts[1:]))

                    path = LocationPath('file').joinpath(path.as_posix().lstrip('/'))

                parts = path.parent.parts
                dir_parts = dir_path.parts

                k = 0
                for item1, item2 in zip(parts, dir_parts):
                    if item1 != item2:
                        break
                    k += 1

                if not k:
                    prefix = '/'.join(['..'] * len(dir_parts))
                    repl_path = LocationPath(prefix).joinpath(path)
                else:
                    repl_path = LocationPath('/'.join(parts[k:])).joinpath(path.name)
                    if k < len(dir_parts):
                        prefix = '/'.join(['..'] * (len(dir_parts) - k))
                        repl_path = LocationPath(prefix).joinpath(repl_path)

                repl = repl_path.as_posix()
                logger.debug("Replace location %r with %r", location, repl)

                exports[schema][1] = replace_location(exports[schema][1], location, repl)
                modified_schemas.add(schema)

                if ref_schema not in exports:
                    exports[ref_schema] = [path, ref_schema.get_text(), False]

            if remove_residuals:
                # Deactivate residual redundant imports from remote URLs
                for location in filter(residuals_filter, schema_locations):
                    logger.debug("Clear residual remote location %r", location)
                    exports[schema][1] = replace_location(exports[schema][1], location, '')
                    modified_schemas.add(schema)

        if current_length == len(exports):
            break

    for schema, (path, text, processed) in exports.items():
        assert processed

        filepath = target_path.joinpath(path)

        # Safety check: raise error if filepath is not inside the target path
        try:
            filepath.resolve(strict=False).relative_to(target_path.resolve(strict=False))
        except ValueError:
            msg = _("target directory {} violation for exported path {}, {}")
            raise XMLSchemaValueError(msg.format(target_dir, str(path), str(filepath)))

        if not filepath.parent.exists():
            filepath.parent.mkdir(parents=True)

        encoding = 'utf-8'  # default encoding for XML 1.0

        if text.startswith('<?'):
            # Get the encoding from XML declaration
            xml_declaration = text.split('\n', maxsplit=1)[0]
            re_match = re.search('(?<=encoding=["\'])[^"\']+', xml_declaration)
            if re_match is not None:
                encoding = re_match.group(0).lower()

        if schema in modified_schemas:
            logger.debug("Write modified XSD source to %s", filepath)
        else:
            logger.debug("Write unchanged XSD source to %s", filepath)

        with filepath.open(mode='w', encoding=encoding) as fp:
            fp.write(text)
