# -*- coding: utf-8 -*-
#
# Copyright (c), 2016, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from .exceptions import XMLSchemaNotBuiltError, XMLSchemaValidationError
from .utils import check_value


class XMLSchemaValidator(object):
    """
    Base class for defining XML Schema validators. The validator uses two tokens,
    one for building and the other for validity check, because a schema could
    contains circular definitions. Those tokens are usually managed by the object
    that contains the global maps, and the implementations of the validator has to
    define two properties that returns the value of those tokens.
    """
    def __init__(self):
        self._check_token = None    # Token for managing checks without circularity
        self._valid = None          # True == 'valid', False == 'invalid', None == 'notKnown'

    def __setattr__(self, name, value):
        if name == '_valid':
            check_value(value, None, True, False)
        super(XMLSchemaValidator, self).__setattr__(name, value)

    @property
    def check_token(self):
        """
        Get the reference token for verify the check status of the validator.
        """
        raise NotImplementedError

    @property
    def built(self):
        """
        Returns the validator built status, `True` if the validator has been \
        fully built, `False` otherwise.
        """
        raise NotImplementedError

    @property
    def checked(self):
        """
        Returns the validator built status, `True` if the validator has been \
        fully checked, `False` otherwise.
        """
        if not self.built:
            return False
        return self._check_token == self.check_token

    @property
    def valid(self):
        if self.checked:
            return self._valid
        else:
            return None

    @property
    def validity(self):
        """
        Ref: https://www.w3.org/TR/xmlschema-1/#e-validity
        Ref: https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#e-validity
        """
        if self.checked and self.built:
            if self._valid is True:
                return 'valid'
            elif self._valid is False:
                return 'invalid'
        return 'notKnown'

    @property
    def validation_attempted(self):
        """
        Ref: https://www.w3.org/TR/xmlschema-1/#e-validation_attempted
        Ref: https://www.w3.org/TR/2012/REC-xmlschema11-1-20120405/#e-validation_attempted
        """
        if self.valid is True:
            return 'full'
        elif self.valid is False:
            return 'partial'
        elif self.built is False:
            return 'none'
        else:
            return 'partial'  # the instance was already parsed in any case ...

    def check(self):
        #if not self.built:
        #    raise XMLSchemaNotBuiltError("%r is not built." % self)
        self._check_token = self.check_token
        if not self.built:
            self._valid = None
            import pdb
            pdb.set_trace()
            print("%r not built" % self, repr(self.parent))
            # raise XMLSchemaNotBuiltError("%r: cannot check a not built component." % self)
        else:
            self._valid = True

    def validate(self, data, use_defaults=True):
        """
        Validates XML data using the XSD component.

        :param data: the data source containing the XML data. Can be a string for an \
        attribute or a simple type definition, or an ElementTree's Element for \
        other XSD components.
        :param use_defaults: Use schema's default values for filling missing data.
        :raises: :exc:`XMLSchemaValidationError` if the object is not valid.
        """
        for error in self.iter_errors(data, use_defaults=use_defaults):
            raise error

    def iter_errors(self, data, path=None, use_defaults=True):
        """
        Creates an iterator for errors generated validating XML data with
        the XSD component.

        :param data: the object containing the XML data. Can be a string for an \
        attribute or a simple type definition, or an ElementTree's Element for \
        other XSD components.
        :param path:
        :param use_defaults: Use schema's default values for filling missing data.
        """
        for chunk in self.iter_decode(data, path, use_defaults=use_defaults, skip_errors=True):
            if isinstance(chunk, XMLSchemaValidationError):
                yield chunk

    def is_valid(self, data, use_defaults=True):
        error = next(self.iter_errors(data, use_defaults=use_defaults), None)
        return error is None

    def decode(self, data, *args, **kwargs):
        """
        Decodes XML data using the XSD component.

        :param data: the object containing the XML data. Can be a string for an \
        attribute or a simple type definition, or an ElementTree's Element for \
        other XSD components.
        :param args: arguments that maybe passed to :func:`XMLSchema.iter_decode`.
        :param kwargs: keyword arguments from the ones included in the optional \
        arguments of the :func:`XMLSchema.iter_decode`.
        :return: A dictionary like object if the XSD component is an element, a \
        group or a complex type; a list if the XSD component is an attribute group; \
         a simple data type object otherwise.
        :raises: :exc:`XMLSchemaValidationError` if the object is not decodable by \
        the XSD component, or also if it's invalid when ``validate=True`` is provided.
        """
        for chunk in self.iter_decode(data, *args, **kwargs):
            if isinstance(chunk, XMLSchemaValidationError):
                raise chunk
            return chunk
    to_dict = decode

    def encode(self, data, *args, **kwargs):
        for chunk in self.iter_encode(data, *args, **kwargs):
            if isinstance(chunk, XMLSchemaValidationError):
                raise chunk
            return chunk
    to_etree = encode

    def iter_decode(self, data, path=None, process_namespaces=True, validate=True,
                    namespaces=None, use_defaults=True, skip_errors=False, decimal_type=None,
                    converter=None, dict_class=None, list_class=None):
        """
        Generator method for decoding XML data using the XSD component. Returns a data
        structure after a sequence, possibly empty, of validation or decode errors
        (decode errors only if the optional argument *validate* is `False`).

        Like the method *decode* except that it does not raise any exception. Yields
        decoded values. Also :exc:`XMLSchemaValidationError` errors are yielded during
        decoding process if the *obj* is invalid.
        """
        raise NotImplementedError

    def iter_encode(self, data, path=None, validate=True, namespaces=None, skip_errors=False,
                    indent=None, element_class=None, converter=None):
        """

        :param data:
        :param path:
        :param validate:
        :param namespaces:
        :param skip_errors:
        :param indent:
        :param element_class: Element class to use when encode data to an ElementTree \
        structure. Default is `xml.etree.ElementTree.Element`.
        :param converter:
        :return:
        """
        raise NotImplementedError
