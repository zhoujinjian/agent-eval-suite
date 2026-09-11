# conftest.py —— pytest 会自动把本文件所在的目录加入 sys.path。
# 放在 agent-eval/ 根目录，deepeval/ collector/ verifier/ 就能互相导入，
# 测试文件里不需要 sys.path.insert 这种运行时 hack。
#
# 这是 pytest 的标准约定：conftest.py 所在目录 = 项目的导入根目录。
