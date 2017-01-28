import numpy as np


from .table import PoolTable
from .physics import PoolPhysics


INCH2METER = 0.0254


class PoolGame(object):
    BALL_COLORS = [0xddddde,
                   0xeeee00,
                   0x0000ee,
                   0xee0000,
                   0xee00ee,
                   0xee7700,
                   0x00ee00,
                   0xbb2244,
                   0x111111]
    BALL_COLORS = BALL_COLORS + BALL_COLORS[1:-1]
    def __init__(self, ball_colors=BALL_COLORS, **kwargs):
        table = PoolTable(**kwargs)
        self.table = table
        self.ball_colors = ball_colors
        self.num_balls = len(ball_colors)
        self.ball_positions = np.empty((self.num_balls, 3), dtype=np.float32)
        self.initial_positions(out=self.ball_positions)
        self.physics = PoolPhysics(num_balls=self.num_balls)
    def initial_positions(self, d=None, out=None):
        ball_radius = self.table.ball_radius
        if d is None:
            d = 0.04 * ball_radius
        if out is None:
            out = np.empty((self.num_balls, 3), dtype=np.float32)
        H_table = self.table.H_table
        L_table = self.table.L_table
        ball_diameter = 2 * ball_radius
        # triangle racked:
        out[:,1] = H_table + ball_radius + 0.0001
        side_length = 4 * (ball_diameter + d)
        x_positions = np.concatenate([np.linspace(0,                        0.5 * side_length,                         5),
                                      np.linspace(-0.5*(ball_diameter + d), 0.5 * side_length - (ball_diameter + d),   4),
                                      np.linspace(-(ball_diameter + d),     0.5 * side_length - 2*(ball_diameter + d), 3),
                                      np.linspace(-1.5*(ball_diameter + d), 0.5 * side_length - 3*(ball_diameter + d), 2),
                                      np.array([-2*(ball_diameter + d)])])
        z_positions = np.concatenate([np.linspace(0,                                    np.sqrt(3)/2 * side_length, 5),
                                      np.linspace(0.5*np.sqrt(3) * (ball_diameter + d), np.sqrt(3)/2 * side_length, 4),
                                      np.linspace(np.sqrt(3) * (ball_diameter + d),     np.sqrt(3)/2 * side_length, 3),
                                      np.linspace(1.5*np.sqrt(3) * (ball_diameter + d), np.sqrt(3)/2 * side_length, 2),
                                      np.array([np.sqrt(3)/2 * side_length])])
        z_positions *= -1
        z_positions -= L_table / 8
        out[1:,0] = x_positions
        out[1:,2] = z_positions
        # cue ball at head spot:
        out[0,0] = 0.0
        out[0,2] = 0.25 * L_table
        return out