" lua << EOF
" require('lazy-loader')()
" EOF

let g:gutentags_ctags_exclude += ['*/.venv/*', '*/benchmark-tests/*']
let g:projectionist_heuristics = {
      \ 'pyproject.toml': {
      \   'whorl/*.py': {
      \     'type': 'function',
      \     'alternate': [
      \       'tests/{dirname}test_{basename}.py',
      \       'tests/{dirname}/test_{basename}.py',
      \     ]
      \   },
      \   'tests/**/test_*.py': {
      \     'type': 'test',
      \     'alternate': [
      \       'whorl/{dirname}{basename}.py',
      \       'whorl/{dirname}/{basename}.py',
      \     ]
      \   },
      \ },
      \ }
