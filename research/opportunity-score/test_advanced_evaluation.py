import importlib.util
import unittest
from pathlib import Path
import numpy as np
import polars as pl

spec=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('test_advanced_models.py'))
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class TemporalEvaluationTests(unittest.TestCase):
    def test_imputation_uses_training_only_and_marks_missing(self):
        a,b=audit.design(pl.DataFrame({'x':[2.,4.,None]}),pl.DataFrame({'x':[1000.,None]}),['x'])
        self.assertEqual(a[2,1],3.)
        self.assertEqual(b[1,1],3.)
        self.assertEqual(b[1,2],1.)
        self.assertEqual(b[0,1],1000.)

    def test_next_week_prediction_does_not_use_next_week_score(self):
        test=pl.DataFrame({'player_id':['p','p'],'week':[1,2],'team':['DET','DET'],'pts_half':[7.,50.]})
        prev=pl.DataFrame({'player_id':['p'],'week':[18],'team':['DET'],'pts_half':[4.]})
        a=audit.forecasts(test,np.array([2.,100.]),prev,np.array([4.]),'RB','half',{(2,'DET'),(3,'DET')})
        b=audit.forecasts(test,np.array([2.,0.]),prev,np.array([4.]),'RB','half',{(2,'DET'),(3,'DET')})
        self.assertEqual(a[0]['ewma'],b[0]['ewma'])
        self.assertAlmostEqual(a[0]['ewma'],3.3)
        self.assertFalse(a[1]['observed'])
        self.assertEqual(a[1]['actual'],0.)
        self.assertEqual(len(audit.forecasts(test,np.array([2.,100.]),prev,np.array([4.]),'RB','half',{(2,'DET')})),1)


if __name__=='__main__':unittest.main()
