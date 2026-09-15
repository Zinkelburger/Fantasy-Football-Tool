"""Run with the league-sim Python; no network calls."""
import unittest
import numpy as np
import polars as pl
import ep_model


class PassingTouchdownScoring(unittest.TestCase):
    def test_six_point_actuals_add_only_passing_touchdown_bonus(self):
        stats=pl.DataFrame({'season_type':['REG']*3,'season':[2026]*3,'week':[1]*3,
            'player_id':['passer','rusher','receiver'],'player_display_name':['A','B','C'],
            'position':['QB','QB','WR'],'passing_tds':[3,0,0],
            'fantasy_points':[20.,20.,8.],'fantasy_points_ppr':[20.,20.,12.]})
        result=ep_model.actuals(stats).to_dicts()
        for row,bonus in zip(result,[6,0,0]):
            for fmt in ('std','half','ppr'):
                self.assertEqual(row['pts_'+fmt+'6']-row['pts_'+fmt],bonus)

    def test_expected_bonus_is_fitted_from_usage_not_observed_tds(self):
        x=np.arange(1,31,dtype=float)
        td=(x%4).astype(float)
        frame=pl.DataFrame({'pass_att':x,'pts_half':2+x*.3,'pts_half6':2+x*.3+2*td})
        c4=ep_model._fit(frame,['pass_att'],'pts_half')
        c6=ep_model._fit(frame,['pass_att'],'pts_half6')
        p4=c4['_intercept']+c4['pass_att']*x
        p6=c6['_intercept']+c6['pass_att']*x
        self.assertFalse(np.allclose(p6,p4+2*td))
        self.assertFalse(np.allclose(p6,p4*1.5))
        self.assertAlmostEqual(float(np.mean(p6-p4)),float(np.mean(2*td)))


if __name__=='__main__': unittest.main()
