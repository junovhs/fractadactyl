"""PROB-21 combinatorial incidence, exact decimals and view selection."""
import json
from pathlib import Path
import tempfile
import unittest

import mpmath as mp

import hubbard


class HubbardTests(unittest.TestCase):
    def test_known_triod_trees(self):
        for angle,q,p,arms,nodes,edges in [('1/6',2,2,3,5,4),('1/2',2,1,2,3,2)]:
            n,e,nu=hubbard.abstract_tree(angle,q,p)
            self.assertEqual((len(n),len(e)),(nodes,edges))
            self.assertEqual(max(x['arms'] for x in n),arms)
            self.assertEqual(sum(x['arms'] for x in n),2*len(e))
            self.assertIn('(',nu)

    def test_orbit_and_v0_non_fabrication(self):
        with mp.workdps(85):
            i=hubbard.build_case('i','0','1',2,2,angle='1/6')
            tip=hubbard.build_case('tip','-2','0',2,1,angle='1/2')
            v0=hubbard.build_case('v0',*hubbard.V0,24,2)
        self.assertEqual((i['q'],i['p'],i['metrics']['max_arms']),(2,2,3))
        self.assertEqual((tip['q'],tip['p'],tip['metrics']['max_arms']),(2,1,2))
        self.assertEqual((v0['q'],v0['p']), (24,2))
        self.assertLess(mp.mpf(v0['residual']),mp.mpf('1e-65'))
        self.assertIsNone(v0['metrics']['max_arms'])
        self.assertEqual(v0['nodes'],[])

    def test_angle_and_failure_contract(self):
        self.assertEqual(hubbard.angle_period(hubbard.Fraction(1,6)),(1,2))
        self.assertEqual(hubbard.angle_period(hubbard.Fraction(1,2)),(1,1))
        self.assertEqual(hubbard.kneading('1/6').signature(5),'11010')
        with self.assertRaises(ValueError):
            hubbard.build_case('not-the-ray','0','1',2,2,angle='1/2')
        with self.assertRaises(ValueError):
            hubbard.build_case('non-repelling','0','0',1,1)

    def test_view_predicates_are_recomputed_and_unique(self):
        i=hubbard.build_case('i','0','1',2,2,angle='1/6')
        tip=hubbard.build_case('tip','-2','0',2,1,angle='1/2')
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'docs/research/shapes'
            hubbard.output([i,tip],out)
            views=json.loads((out/'views.json').read_text())
            self.assertEqual(len(views),len({(v['re'],v['im'],v['width']) for v in views}))
            for v in views:
                case=next(c for c in (i,tip) if c['name']==v['case'])
                flag,metrics=hubbard.metrics_for_view(case,v['width'],v['shape'])
                self.assertEqual((flag,metrics), (v['expected'],v['values']))
                self.assertTrue(v['image'].startswith('img/'))
                self.assertGreater(mp.mpf(v['width']),0)
            text=(out/'contact-sheet.md').read_text()
            self.assertIn('![](img/',text)
            self.assertIn('**New (unproved):**',text)
            self.assertIn('INSUFFICIENT',text)
            cmds=(out/'render.sh').read_text()
            self.assertEqual(cmds.count('"$FD" render '),len(views))
            self.assertEqual(cmds.count('"$FD" shade '),len(views))
            self.assertIn('--size 320x180',cmds)


if __name__=='__main__':
    unittest.main()
