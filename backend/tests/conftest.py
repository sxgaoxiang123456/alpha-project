import os
import sys

# 项目根目录加入 sys.path，确保 backend 包可被导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
