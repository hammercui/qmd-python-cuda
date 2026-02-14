import unittest
import os
from pathlib import Path
from qmd.models.config import AppConfig, CollectionConfig

class TestConfig(unittest.TestCase):
    def setUp(self):
        self.test_yaml = Path("test_index.yml")
    
    def tearDown(self):
        if self.test_yaml.exists():
            os.remove(self.test_yaml)

    def test_save_load(self):
        config = AppConfig(db_path="custom.db")
        config.collections.append(CollectionConfig(name="test", path="/tmp"))
        config.save(self.test_yaml)
        
        self.assertTrue(self.test_yaml.exists())
        
        loaded = AppConfig.load(self.test_yaml)
        self.assertEqual(loaded.db_path, "custom.db")
        self.assertEqual(len(loaded.collections), 1)
        self.assertEqual(loaded.collections[0].name, "test")

    def test_load_non_existent(self):
        loaded = AppConfig.load(Path("non_existent.yml"))
        # Should return default config
        self.assertEqual(len(loaded.collections), 0)
        self.assertTrue(loaded.db_path.endswith("qmd.db"))
