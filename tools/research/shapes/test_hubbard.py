"""PROB-21 numerical contracts and non-fabrication check."""
import json
from pathlib import Path
import tempfile
import unittest

import mpmath as mp
import hubbard


class HubbardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i=hubbard.build_case('i','0','1',2,2)
        cls.tip=hubbard.build_case('tip','-2','0',2,1)
        cls.v0=hubbard.build_case('v0',*hubbard.V0,24,2)

    def test_orbits_and_proxy_arms(self):
        self.assertEqual((self.i['q'],self.i['p']),(2,2))
        self.assertEqual(self.i['metrics']['max_arms'],3)
        self.assertEqual((self.tip['q'],self.tip['p']),(2,1))
        self.assertEqual(self.tip['metrics']['max_arms'],2)
        self.assertEqual(self.tip['metrics']['forks'],0)
        self.assertEqual((self.v0['q'],self.v0['p']),(24,2))
        self.assertLess(mp.mpf(self.v0['residual']),mp.mpf('1e-70'))
        self.assertEqual(self.v0['metrics']['max_arms'],3)

    def test_discovery_rejection_and_angles(self):
        self.assertEqual(hubbard.discover(mp.mpc(0,1)),(2,2))
        self.assertEqual(hubbard.discover(mp.mpc(-2,0)),(2,1))
        self.assertEqual(hubbard.angle_period(hubbard.Fraction(1,6)),(1,2))
        self.assertEqual(hubbard.angles_checked(['1/6'],2,2),['1/6'])
        with self.assertRaises(ValueError):
            hubbard.angles_checked(['1/3'],2,2)
        with self.assertRaisesRegex(ValueError,'non-minimal'):
            hubbard.build_case('wrong','0','1',4,2)
        with self.assertRaises(ValueError):
            hubbard.build_case('superattracting','0','0',1,1)

    def test_plan_is_falsifiable(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'out'
            sheet=Path(directory)/'contact-sheet.md'
            cases=[self.i,self.tip,self.v0]
            hubbard.output(cases,out,sheet)
            views=json.loads((out/'views.json').read_text())
            for v in views:
                c=next(x for x in cases if x['name']==v['case'])
                self.assertEqual(v['predicted'],c['fires'][v['shape']])
                self.assertGreater(mp.mpf(v['width']),0)
            script=(out/'render.sh').read_text()
            self.assertEqual(script.count('"$FD" render '),len(views))
            self.assertEqual(script.count('"$FD" shade '),len(views))
            self.assertIn('Insufficient cases',sheet.read_text())
            self.assertIn('Not a Hubbard-tree reconstruction',sheet.read_text())


if __name__=='__main__':
    unittest.main()
