import sys
import os.path
import logging
from collections import defaultdict
import argparse
import numpy as np
import OpenGL
OpenGL.ERROR_CHECKING = False
OpenGL.ERROR_LOGGING = False
OpenGL.ERROR_ON_COPY = True
import OpenGL.GL as gl
import cyglfw3 as glfw


from gl_rendering import *
try:
    from pyopenvr_renderer import OpenVRRenderer
except ImportError as err:
    OpenVRRenderer = None


MOVE_SPEED = 0.3
CUE_MOVE_SPEED = 0.3
TURN_SPEED = 1.2
MOUSE_MOVE_SPEED = 0.04
MOUSE_CUE_MOVE_SPEED = 0.08
BG_COLOR = (0.0, 0.0, 0.0, 0.0)

_logger = logging.getLogger(__name__)


def setup_glfw(width=800, height=600, double_buffered=False):
    if not glfw.Init():
        raise Exception('failed to initialize glfw')
    if not double_buffered:
        glfw.WindowHint(glfw.DOUBLEBUFFER, False)
        glfw.SwapInterval(0)
    window = glfw.CreateWindow(width, height, "gltfview")
    if not window:
        glfw.Terminate()
        raise Exception('failed to create glfw window')
    glfw.MakeContextCurrent(window)
    print('GL_VERSION: %s' % gl.glGetString(gl.GL_VERSION))
    return window


def main(window_size=(800,600), novr=False):
    window = setup_glfw(width=window_size[0], height=window_size[1], double_buffered=novr)
    if not novr and OpenVRRenderer is not None:
        try:
            renderer = OpenVRRenderer(window_size=window_size)
        except openvr.OpenVRError as err:
            print('could not initialize OpenVRRenderer: %s' % err)
            renderer = OpenGLRenderer(window_size=window_size)
    else:
        renderer = OpenGLRenderer(window_size=window_size, znear=0.1, zfar=1000)
    gl.glViewport(0, 0, window_size[0], window_size[1])
    def on_resize(window, width, height):
        gl.glViewport(0, 0, width, height)
        renderer.window_size = (width, height)
        renderer.update_projection_matrix()
    glfw.SetWindowSizeCallback(window, on_resize)
    glfw.SetInputMode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)
    mouse_button_state = defaultdict(int)
    def on_mousedown(window, button, action, mods):
        if action == glfw.PRESS:
            mouse_button_state[button] = True
        elif action == glfw.RELEASE:
            mouse_button_state[button] = False
    glfw.SetMouseButtonCallback(window, on_mousedown)
    key_state = defaultdict(bool)
    def on_keydown(window, key, scancode, action, mods):
        if key == glfw.KEY_ESCAPE and action == glfw.PRESS:
            glfw.SetWindowShouldClose(window, gl.GL_TRUE)
        elif action == glfw.PRESS:
            key_state[key] = True
        elif action == glfw.RELEASE:
            key_state[key] = False
    glfw.SetKeyCallback(window, on_keydown)
    camera_world_matrix = renderer.camera_matrix
    camera_position = camera_world_matrix[3,:3]
    cursor_pos = glfw.GetCursorPos(window)
    theta = 0.0
    def process_input(dt):
        glfw.PollEvents()
        pos = glfw.GetCursorPos(window)
        nonlocal cursor_pos
        dx, dy = pos[0] - cursor_pos[0], pos[1] - cursor_pos[1]
        cursor_pos = pos
        nonlocal theta
        theta += TURN_SPEED * dt * (key_state[glfw.KEY_LEFT] - key_state[glfw.KEY_RIGHT])
        if theta >= np.pi:
            theta -= 2*np.pi
        elif theta < -np.pi:
            theta += 2*np.pi
        sin, cos = np.sin(theta), np.cos(theta)
        camera_world_matrix[0,0] = cos
        camera_world_matrix[0,2] = -sin
        camera_world_matrix[2,0] = sin
        camera_world_matrix[2,2] = cos
        fb = MOVE_SPEED * dt * (-key_state[glfw.KEY_W] + key_state[glfw.KEY_S])
        lr = MOVE_SPEED * dt * (key_state[glfw.KEY_D] - key_state[glfw.KEY_A])
        ud = MOVE_SPEED * dt * (key_state[glfw.KEY_Q] - key_state[glfw.KEY_Z])
        camera_position[:] += fb * camera_world_matrix[2,:3] + lr * camera_world_matrix[0,:3] + ud * camera_world_matrix[1,:3]
    meshes = []
    gl.glClearColor(*BG_COLOR)
    gl.glEnable(gl.GL_DEPTH_TEST)
    print('* starting render loop...')
    sys.stdout.flush()
    nframes = 0
    lt = glfw.GetTime()
    while not glfw.WindowShouldClose(window):
        t = glfw.GetTime()
        dt = t - lt
        lt = t
        process_input(dt)
        renderer.process_input()
        with renderer.render(meshes=meshes) as frame_data:
            if frame_data:
                poses, velocities, angular_velocities = frame_data
            else:
                pass
        if nframes == 0:
            st = glfw.GetTime()
        nframes += 1
        glfw.SwapBuffers(window)
    print('* FPS (avg): %f' % ((nframes - 1) / (t - st)))
    renderer.shutdown()
    glfw.DestroyWindow(window)
    glfw.Terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--novr", help="non-VR mode", action="store_true")
    args = parser.parse_args()
    main(novr=args.novr)
