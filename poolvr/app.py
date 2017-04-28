import sys
import os.path
import logging
import numpy as np
import OpenGL
OpenGL.ERROR_CHECKING = False
OpenGL.ERROR_LOGGING = False
OpenGL.ERROR_ON_COPY = True
import OpenGL.GL as gl
import cyglfw3 as glfw


_logger = logging.getLogger('poolvr')


from .gl_rendering import OpenGLRenderer, set_matrix_from_quaternion, set_quaternion_from_matrix
try:
    from .pyopenvr_renderer import openvr, OpenVRRenderer
except ImportError as err:
    _logger.warning('could not import pyopenvr_renderer:\n%s', err)
    _logger.warning('\n\n\n**** VR FEATURES ARE NOT AVAILABLE! ****\n\n\n')
    OpenVRRenderer = None
# from .gl_text import TexturedText
from .cue import PoolCue
from .game import PoolGame
from .keyboard_controls import init_keyboard
from .mouse_controls import init_mouse
from .sound import init_sound
try:
    from .ode_physics import ODEPoolPhysics
except ImportError as err:
    _logger.warning('could not import ode_physics:\n%s', err)
    ODEPoolPhysics = None


BG_COLOR = (0.0, 0.0, 0.0, 0.0)


# TODO: pkgutils way
TEXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            os.path.pardir,
                            'textures')


def setup_glfw(width=800, height=600, double_buffered=False, title="poolvr.py 0.0.1", multisample=0):
    if not glfw.Init():
        raise Exception('failed to initialize glfw')
    if not double_buffered:
        glfw.WindowHint(glfw.DOUBLEBUFFER, False)
        glfw.SwapInterval(0)
    window = glfw.CreateWindow(width, height, title)
    if not window:
        glfw.Terminate()
        raise Exception('failed to create glfw window')
    glfw.MakeContextCurrent(window)
    _logger.info('GL_VERSION: %s', gl.glGetString(gl.GL_VERSION))
    renderer = OpenGLRenderer(window_size=(width, height), znear=0.1, zfar=1000)
    def on_resize(window, width, height):
        gl.glViewport(0, 0, width, height)
        renderer.window_size = (width, height)
        renderer.update_projection_matrix()
    glfw.SetWindowSizeCallback(window, on_resize)
    return window, renderer


def main(window_size=(800,600),
         novr=False,
         use_simple_ball_collisions=False,
         use_ode_physics=False,
         multisample=0,
         use_bb_particles=False):
    """
    The main routine.

    Performs initializations, setups, kicks off the render loop.
    """
    _logger.info('HELLO')
    game = PoolGame(use_simple_ball_collisions=use_simple_ball_collisions)
    cue = PoolCue()
    if use_ode_physics and ODEPoolPhysics is not None:
        game.physics = ODEPoolPhysics(num_balls=game.num_balls,
                                      ball_radius=game.ball_radius,
                                      initial_positions=game.ball_positions,
                                      table=game.table)
        cue_body, cue_geom = game.physics.add_cue(cue)
    physics = game.physics
    cue.position[1] = game.table.height + 0.1
    cue_quaternion = np.zeros(4, dtype=np.float32)
    cue_quaternion[3] = 1
    game.reset()
    ball_meshes = game.table.setup_balls(game.ball_radius, game.ball_colors[:9], game.ball_positions,
                                         striped_balls=set(range(9, game.num_balls)),
                                         use_billboards=use_bb_particles)
    window, fallback_renderer = setup_glfw(width=window_size[0], height=window_size[1], double_buffered=novr, multisample=multisample)
    if not novr and OpenVRRenderer is not None:
        try:
            renderer = OpenVRRenderer(window_size=window_size, multisample=multisample)
            button_press_callbacks = {openvr.k_EButton_Grip: game.reset,
                                      openvr.k_EButton_ApplicationMenu: game.advance_time}
            if ODEPoolPhysics is not None:
                def on_cue_ball_collision(renderer=renderer, game=game, physics=physics, impact_speed=None):
                    if impact_speed:
                        renderer.vr_system.triggerHapticPulse(renderer._controller_indices[0], 0,
                                                              int(max(1.0, impact_speed**2 / 2.0) * 2500))
                    game.ntt = physics.next_turn_time()
                physics.set_cue_ball_collision_callback(on_cue_ball_collision)
                def on_cue_surface_collision(renderer=renderer, game=game, physics=physics, impact_speed=None):
                    if impact_speed > 0.005:
                        renderer.vr_system.triggerHapticPulse(renderer._controller_indices[0], 0,
                                                              int(max(1.0, impact_speed**2 * 1.2 / 2.0) * 2500))
        except Exception as err:
            renderer = fallback_renderer
            _logger.error('could not initialize OpenVRRenderer: %s', err)
    else:
        renderer = fallback_renderer
        renderer.camera_position[1] = game.table.height + 0.6
        renderer.camera_position[2] = game.table.length - 0.1
    camera_world_matrix = fallback_renderer.camera_matrix
    camera_position = camera_world_matrix[3,:3]

    process_keyboard_input = init_keyboard(window)
    process_mouse_input = init_mouse(window)
    def process_input(dt):
        glfw.PollEvents()
        process_keyboard_input(dt, camera_world_matrix, cue)
        process_mouse_input(dt, cue)

    # textured_text = TexturedText()

    meshes = [game.table.mesh] + ball_meshes + [cue]
    for mesh in meshes:
        mesh.init_gl()

    ball_positions = game.ball_positions.copy()
    ball_quaternions = game.ball_quaternions
    ball_mesh_positions = [mesh.world_matrix[3,:3] for mesh in ball_meshes]
    ball_mesh_rotations = [mesh.world_matrix[:3,:3].T for mesh in ball_meshes]

    gl.glViewport(0, 0, window_size[0], window_size[1])
    gl.glClearColor(*BG_COLOR)
    gl.glEnable(gl.GL_DEPTH_TEST)

    init_sound()

    _logger.info('entering render loop...')
    sys.stdout.flush()

    nframes = 0
    max_frame_time = 0.0
    lt = glfw.GetTime()
    while not glfw.WindowShouldClose(window):
        t = glfw.GetTime()
        dt = t - lt
        lt = t
        process_input(dt)

        with renderer.render(meshes=meshes) as frame_data:

            ##### VR mode: #####

            if isinstance(renderer, OpenVRRenderer) and frame_data:
                renderer.process_input(button_press_callbacks=button_press_callbacks)
                hmd_pose = frame_data['hmd_pose']
                camera_position[:] = hmd_pose[:,3]
                for i, pose in enumerate(frame_data['controller_poses'][:1]):
                    velocity = frame_data['controller_velocities'][i]
                    angular_velocity = frame_data['controller_angular_velocities'][i]
                    cue.world_matrix[:3,:3] = pose[:,:3].dot(cue.rotation).T
                    cue.world_matrix[3,:3] = pose[:,3]
                    cue.velocity[:] = velocity
                    cue.angular_velocity = angular_velocity
                    set_quaternion_from_matrix(pose[:,:3], cue_quaternion)
                    # if game.t >= game.ntt:
                    #     for i, position in cue.aabb_check(ball_positions, ball_radius):
                    #         if game.t - last_contact_t[i] < 0.02:
                    #             continue
                    #         poc = cue.contact(position, ball_radius)
                    #         if poc is not None:
                    #             renderer.vr_system.triggerHapticPulse(renderer._controller_indices[-1],
                    #                                                   0, int(np.linalg.norm(cue.velocity + np.cross(position, cue.angular_velocity))**2 / 2.0 * 2700))
                    #             poc[:] = [0.0, 0.0, ball_radius]
                    #             # physics.strike_ball(game.t, i, poc, cue.velocity, cue.mass)
                    #             game.ntt = physics.next_turn_time()
                    #             break

            ##### desktop mode: #####

            elif isinstance(renderer, OpenGLRenderer):
                set_quaternion_from_matrix(cue.rotation.dot(cue.world_matrix[:3,:3].T),
                                           cue_quaternion)
                # if game.t >= game.ntt:
                #     for i, position in cue.aabb_check(ball_positions, ball_radius):
                #         poc = cue.contact(position, ball_radius)
                #         if poc is not None:
                #             poc[:] = [0.0, 0.0, ball_radius]
                #             physics.strike_ball(game.t, i, poc, cue.velocity, cue.mass)
                #             game.ntt = physics.next_turn_time()
                #             break

            cue_body.setPosition(cue.world_position)
            #cue_geom.setPosition(cue_position)
            x, y, z, w = cue_quaternion
            cue_body.setQuaternion((w, x, y, z))
            cue_geom.setQuaternion((w, x, y, z))
            cue_body.setLinearVel(cue.velocity)
            cue_body.setAngularVel(cue.angular_velocity)

            physics.eval_positions(game.t, out=ball_positions)
            physics.eval_quaternions(game.t, out=ball_quaternions)
            ball_positions[~physics.on_table] = camera_position # hacky way to only show balls that are on table
            for i, pos in enumerate(ball_positions):
                ball_mesh_positions[i][:] = pos
            for i, quat in enumerate(ball_quaternions):
                set_matrix_from_quaternion(quat, ball_mesh_rotations[i])
            # ball_billboards.update_gl()
            # textured_text.set_text("%9.3f" % dt)
            # textured_text.update_gl()

        game.t += dt
        physics.step(dt)

        max_frame_time = max(max_frame_time, dt)
        if nframes == 0:
            st = glfw.GetTime()
        nframes += 1
        glfw.SwapBuffers(window)

    _logger.info('...exited render loop: average FPS: %f, maximum frame time: %f',
                 (nframes - 1) / (t - st), max_frame_time)

    renderer.shutdown()
    _logger.info('...shut down renderer')
    glfw.DestroyWindow(window)
    glfw.Terminate()
    _logger.info('GOODBYE')
