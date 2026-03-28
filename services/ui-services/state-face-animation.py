python3 - << 'EOF'
from sense_hat import SenseHat
import time

s = SenseHat()
s.low_light = True

BLUE_DIM = (0, 0, 50)
BLUE     = (0, 0, 255)
ORANGE   = (255, 140, 0)
GREEN    = (0, 200, 0)
RED      = (255, 0, 0)
OFF      = (0, 0, 0)

def make_face(eye_pixels, mouth_pixels, color):
    grid = [OFF] * 64
    for (r, c) in eye_pixels + mouth_pixels:
        grid[r * 8 + c] = color
    return grid

# Spinner: 8 pixels arranged in a circle on the 8x8 grid
# Clockwise order starting top-center
SPINNER_RING = [
    (1,3),(1,4),   # top
    (2,6),(3,6),   # right top
    (4,6),(5,6),   # right bottom  
    (6,4),(6,3),   # bottom
    (5,1),(4,1),   # left bottom
    (3,1),(2,1),   # left top
]

def spinning_loader(duration=3.0, color=ORANGE):
    """Draws a revolving arc (4 lit pixels) around the ring."""
    arc_length = 4
    steps = len(SPINNER_RING)
    frame_delay = 0.08
    frames = int(duration / frame_delay)

    for i in range(frames):
        grid = [OFF] * 64
        for j in range(arc_length):
            idx = (i + j) % steps
            r, c = SPINNER_RING[idx]
            # Fade: head brightest, tail dims
            brightness = 1.0 - (j / arc_length) * 0.75
            grid[r * 8 + c] = tuple(int(v * brightness) for v in color)
        s.set_pixels(grid)
        time.sleep(frame_delay)

# Static faces
standby = make_face(
    eye_pixels=[(2,2),(2,5)],
    mouth_pixels=[(5,2),(5,3),(5,4),(5,5)],
    color=BLUE_DIM
)
listening = make_face(
    eye_pixels=[(1,1),(1,2),(2,1),(2,2),(3,1),(3,2),
                (1,5),(1,6),(2,5),(2,6),(3,5),(3,6)],
    mouth_pixels=[(5,1),(5,2),(5,3),(5,4),(5,5),(5,6)],
    color=BLUE
)
responding = make_face(
    eye_pixels=[(2,1),(2,2),(2,3),(2,5),(2,6),(2,7)],
    mouth_pixels=[(5,1),(5,6),(6,2),(6,3),(6,4),(6,5)],
    color=GREEN
)
error_face = make_face(
    eye_pixels=[(1,1),(1,6),(2,2),(2,5)],
    mouth_pixels=[(6,1),(6,6),(5,2),(5,3),(5,4),(5,5)],
    color=RED
)

# --- Run sequence ---
print("Standby"); s.set_pixels(standby); time.sleep(1.5)
print("Listening"); s.set_pixels(listening); time.sleep(1.5)
print("Processing — spinning loader"); spinning_loader(duration=3.0)
print("Responding"); s.set_pixels(responding); time.sleep(1.5)
print("Error"); s.set_pixels(error_face); time.sleep(1.5)

s.clear()
print("Done")
EOF