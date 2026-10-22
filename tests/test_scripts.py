import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENSURE = ROOT / "scripts" / "ensure_inventory_host.py"
SORT = ROOT / "scripts" / "sort_vault_keys.py"

INVENTORY = """all:
  children:
    remnanodes:
      hosts:
        node1:
          ansible_host: "192.0.2.1"
"""


class EnsureInventoryHostTest(unittest.TestCase):
    def run_ensure(self, inventory: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ENSURE), str(inventory), "node1", "--group", "remnanodes", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_force_replaces_the_address_and_adds_the_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp) / "hosts.yml"
            inventory.write_text(INVENTORY)
            result = self.run_ensure(
                inventory,
                "--ansible-host", "192.0.2.2",
                "--ansible-port", "2222",
                "--force",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = inventory.read_text()
            self.assertIn('ansible_host: "192.0.2.2"', content)
            self.assertIn("ansible_port: 2222", content)
            self.assertNotIn('ansible_host: "192.0.2.1"', content)

    def test_without_force_keeps_the_existing_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp) / "hosts.yml"
            inventory.write_text(INVENTORY)
            result = self.run_ensure(inventory, "--ansible-host", "192.0.2.2")
            self.assertEqual(result.returncode, 0, result.stderr)
            content = inventory.read_text()
            self.assertIn('ansible_host: "192.0.2.1"', content)
            self.assertNotIn("ansible_port", content)
            self.assertIn("FORCE=1", result.stderr)


class SortVaultKeysTest(unittest.TestCase):
    def run_sort(self, vault: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SORT), str(vault)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_sorts_top_level_keys_and_preserves_the_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault.yml"
            vault.write_text("vault_b: 2\nvault_a: 1\n")
            result = self.run_sort(vault)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "2")
            self.assertEqual(vault.read_text(), "vault_a: 1\nvault_b: 2\n")

    def test_refuses_a_file_without_top_level_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault.yml"
            original = "# only a comment\n"
            vault.write_text(original)
            result = self.run_sort(vault)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(vault.read_text(), original)


if __name__ == "__main__":
    unittest.main()
