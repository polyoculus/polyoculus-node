# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os, sys

sys.path.insert(0, os.path.abspath("../.."))

project = 'pyMountOperator'
copyright = '2026, Roban Karthikeyan'
author = 'Roban Karthikeyan'
release = '0.0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon', 
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
]

# Napoleon settings 
napoleon_google_docstring = True # we actually prefer google's docstring style
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

templates_path = ['_templates']
autodoc_member_order = 'bysource'   # keep by the order they appear in source, rather than alphabetical
exclude_patterns = ['_build']    # exclude the doc build folder



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
