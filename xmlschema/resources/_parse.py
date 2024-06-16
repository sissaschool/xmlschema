#
# Copyright (c), 2024, SISSA (International School for Advanced Studies).
# All rights reserved.
# This file is distributed under the terms of the MIT License.
# See the file 'LICENSE' in the root directory of the present
# distribution, or http://opensource.org/licenses/MIT.
#
# @author Davide Brunato <brunato@sissa.it>
#
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from elementpath.protocols import LxmlElementProtocol


def update_ns_declarations(root: LxmlElementProtocol,
                           nsmaps: Dict[LxmlElementProtocol, Dict[str, str]],
                           xmlns: Dict[LxmlElementProtocol, List[Tuple[str, str]]]) -> None:
    """
    Update namespace declarations maps extracting info from a tree of lxml elements.

    :param root: the lxml root element
    :param nsmaps: a dictionary of namespace maps, fully populated with lxml elements.
    :param xmlns: a dictionary of namespace declarations, populated only with lxml \
    elements that have namespace declarations.
    """
    nsmap = {}
    lxml_nsmap = None
    for elem in root.iter():
        if callable(elem.tag):
            nsmaps[elem] = {}
            continue

        if lxml_nsmap != elem.nsmap:
            nsmap = {k or '': v for k, v in elem.nsmap.items()}
            lxml_nsmap = elem.nsmap

        parent = elem.getparent()
        if parent is None:
            ns_declarations = [(k or '', v) for k, v in nsmap.items()]
        elif parent.nsmap != elem.nsmap:
            ns_declarations = [(k or '', v) for k, v in elem.nsmap.items()
                               if k not in parent.nsmap or v != parent.nsmap[k]]
        else:
            ns_declarations = None

        nsmaps[elem] = nsmap
        if ns_declarations:
            xmlns[elem] = ns_declarations
