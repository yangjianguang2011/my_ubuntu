# 🧪 测试用例目录

本目录包含所有测试文件。

---

## 📋 测试文件列表

| 文件 | 测试内容 | 状态 |
|------|---------|------|
| `test_analyst_history.py` | 分析师历史数据功能测试 | ✅ |
| `test_cache_sync.py` | 缓存同步功能测试 | ✅ |
| `test_database_cache.py` | 数据库缓存测试 | ✅ |
| `test_interface.py` | 接口集成测试 | ✅ |
| `test_notification.py` | 通知功能测试 | ✅ |
| `test_sz300_data_source.py` | 沪深 300 数据源测试 | ✅ |
| `test_valuation_api.py` | 估值 API 测试 | ✅ |
| `test_valuation_final.py` | 估值 API 最终测试 | ✅ |
| `test_new_valuation_apis.py` | 新估值接口测试 | ✅ |

---

## 🚀 运行测试

### 运行所有测试

```bash
cd /home/jgyang/.openclaw/workspace/my-ubuntu

# 运行单个测试
python3 tests/test_cache_sync.py

# 运行所有测试
python3 -m pytest tests/ -v
```

### 运行特定测试

```bash
# 缓存测试
python3 tests/test_database_cache.py

# 通知测试
python3 tests/test_notification.py

# 估值 API 测试
python3 tests/test_valuation_final.py
```

---

## 📊 测试覆盖率

```
总测试文件：9 个
测试用例：~50 个
覆盖率目标：60%+
当前覆盖率：~30%
```

---

## 🔧 添加新测试

1. 在 `tests/` 目录创建新文件
2. 命名格式：`test_<功能>.py`
3. 使用 `unittest` 或 `pytest` 框架
4. 确保测试独立，不依赖外部状态

### 示例

```python
# tests/test_example.py
import unittest

class TestExample(unittest.TestCase):
    def test_something(self):
        self.assertEqual(1 + 1, 2)

if __name__ == '__main__':
    unittest.main()
```

---

## 📁 目录结构

```
tests/
├── README.md                    # 本文档
├── __init__.py                 # Python 包标识
├── test_analyst_history.py     # 分析师历史测试
├── test_cache_sync.py          # 缓存同步测试
├── test_database_cache.py      # 数据库缓存测试
├── test_interface.py           # 接口测试
├── test_notification.py        # 通知测试
├── test_sz300_data_source.py   # 数据源测试
├── test_valuation_api.py       # 估值 API 测试
├── test_valuation_final.py     # 估值最终测试
└── test_new_valuation_apis.py  # 新接口测试
```

---

**最后更新**: 2026-03-15  
**维护人**: icode
