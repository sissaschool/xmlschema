#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#

def is_file_object(obj: object) -> bool:
    return hasattr(obj, 'read') and hasattr(obj, 'seekable') \
        and hasattr(obj, 'tell') and hasattr(obj, 'seek') \
        and hasattr(obj, 'closed') and hasattr(obj, 'close')
