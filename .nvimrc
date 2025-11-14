" lua << EOF
" require('lazy-loader')()
" EOF

let g:gutentags_ctags_exclude += ['*/.venv/*', '*/benchmark-tests/*']
let g:projectionist_heuristics = {
      \ 'pyproject.toml': {
      \   'tssim/*.py': {
      \     'type': 'function',
      \     'alternate': [
      \       'tests/{dirname}test_{basename}.py',
      \       'tests/{dirname}/test_{basename}.py',
      \     ]
      \   },
      \   'tests/**/test_*.py': {
      \     'type': 'test',
      \     'alternate': [
      \       'tssim/{dirname}{basename}.py',
      \       'tssim/{dirname}/{basename}.py',
      \     ]
      \   },
      \ },
      \ }
