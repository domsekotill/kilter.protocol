import sys
from pathlib import Path

project = "Kilter (kilter.protocol)"

highlight_language = "python3"

add_module_names = False

html_theme = "sphinx_rtd_theme"

extensions = [
	"sphinx.ext.autodoc",
	"sphinx.ext.doctest",
	"sphinx.ext.viewcode",
	"sphinx.ext.intersphinx",
	"myst_parser",
	"docstring",
]
myst_enable_extensions = [
	"substitution",
]


doc_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(doc_dir))
sys.path.insert(0, str(doc_dir.parent))

autoclass_content = "class"
autodoc_class_signature = "mixed"
autodoc_member_order = "bysource"
autodoc_typehints = "both"
autodoc_typehints_description_target = "documented"
autodoc_typehints_format = "fully-qualified"
autodoc_inherit_docstring = True
doctest_test_doctest_blocks = "default"
myst_heading_anchors = 3

myst_substitutions = {
	"libmilter": "*__libmilter__*",
}

intersphinx_mapping = {
	"python": ("https://docs.python.org/3", None),
}
