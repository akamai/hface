# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "hface"
copyright = "2022 Akamai Technologies"
author = "Miloslav Pojman"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinxcontrib_trio",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented_params"
autodoc_type_aliases = {
    "ByteStream": "ByteStream",
    "DatagramStream": "DatagramStream",
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
html_static_path = ["_static/"]

html_theme_options = {
    "logo": "hface.png",
    "logo_name": True,
    "description": "Hackable HTTP/{1,2,3} {client,server,proxy}",
    "fixed_sidebar": True,
    "show_related": True,
    "show_relbar_bottom": True,
    "extra_nav_links": {
        "GitHub": "https://github.com/akamai/hface",
        "PyPI": "https://pypi.org/project/hface/",
    },
}
