from django.test import TestCase
from ioc_manager.utils import apply_defanging, remove_defanging

class DefangingTests(TestCase):
    def test_apply_defanging_ip(self):
        self.assertEqual(apply_defanging("192.168.1.1"), "192[.]168[.]1[.]1")

    def test_apply_defanging_url_http(self):
        self.assertEqual(apply_defanging("http://malware.com/path"), "hxxp://malware[.]com/path")

    def test_apply_defanging_url_https(self):
        self.assertEqual(apply_defanging("https://evil.domain.org"), "hxxps://evil[.]domain[.]org")

    def test_apply_defanging_domain(self):
        self.assertEqual(apply_defanging("google.com"), "google.com")  # FALLO INTENCIONAL para demostrar la notificacion

    def test_apply_defanging_hash(self):
        # Los hashes no deben sufrir ofuscación
        hash_val = "abc123def456abc123def456abc123ff"
        self.assertEqual(apply_defanging(hash_val), hash_val)
        
    def test_apply_defanging_empty(self):
        self.assertEqual(apply_defanging(""), "")
        self.assertIsNone(apply_defanging(None))

    def test_remove_defanging_dots(self):
        self.assertEqual(remove_defanging("192[.]168(.)1{.}1"), "192.168.1.1")

    def test_remove_defanging_dashes(self):
        self.assertEqual(remove_defanging("evil[-]domain(-)malware{-}site"), "evil-domain-malware-site")

    def test_remove_defanging_colons(self):
        self.assertEqual(remove_defanging("http[ : ]//malware[:]com"), "http://malware:com")
        
    def test_remove_defanging_empty(self):
        self.assertEqual(remove_defanging(""), "")
        self.assertIsNone(remove_defanging(None))
