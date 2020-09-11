import time
import pathlib
import eyed3
from ST7789 import ST7789
from PIL import Image, ImageDraw, ImageFont
import RPi.GPIO as GPIO
from fonts.ttf import RobotoMedium as UserFont
import math
from pygame import mixer


mixer.init()


font = ImageFont.truetype(UserFont, 16)

root = pathlib.Path(__file__).parents[0]
resources = root / "resources"

icon_rightarrow = Image.open(resources / "icon-rightarrow.png").convert("RGBA")
icon_backdrop = Image.open(resources / "icon-backdrop.png").convert("RGBA")
icon_return = Image.open(resources / "icon-return.png").convert("RGBA")


DISPLAY_W = 240
DISPLAY_H = 240

# The buttons on Pirate Audio are connected to pins 5, 6, 16 and 24
# Boards prior to 23 January 2020 used 5, 6, 16 and 20 
# try changing 24 to 20 if your Y button doesn't work.
BUTTONS = [5, 6, 16, 24]

LABELS = ['A', 'B', 'X', 'Y']


def icon(image, icon, position, color):
    col = Image.new("RGBA", icon.size, color=color)
    image.paste(col, position, mask=icon)


def text_in_rect(draw, text, font, rect, line_spacing=1.1, textcolor=(0, 0, 0)):
    x1, y1, x2, y2 = rect
    width = x2 - x1
    height = y2 - y1

    # Given a rectangle, reflow and scale text to fit, centred
    while font.size > 0:
        space_width = font.getsize(" ")[0]
        line_height = int(font.size * line_spacing)
        max_lines = math.floor(height / line_height)
        lines = []

        # Determine if text can fit at current scale.
        words = text.split(" ")

        while len(lines) < max_lines and len(words) > 0:
            line = []

            while (
                len(words) > 0
                and font.getsize(" ".join(line + [words[0]]))[0] <= width
            ):
                line.append(words.pop(0))

            lines.append(" ".join(line))

        if len(lines) <= max_lines and len(words) == 0:
            # Solution is found, render the text.
            y = int(
                y1
                + (height / 2)
                - (len(lines) * line_height / 2)
                - (line_height - font.size) / 2
            )

            bounds = [x2, y, x1, y + len(lines) * line_height]

            for line in lines:
                line_width = font.getsize(line)[0]
                x = int(x1 + (width / 2) - (line_width / 2))
                bounds[0] = min(bounds[0], x)
                bounds[2] = max(bounds[2], x + line_width)
                draw.text((x, y), line, font=font, fill=textcolor)
                y += line_height

            return tuple(bounds)

        font = ImageFont.truetype(font.path, font.size - 1)


class Track:
    def __init__(self, path):
        self.path = path
        self.id3 = eyed3.load(path)

    @property
    def title(self):
        return self.id3.tag.title

    def play(self):
        print(self.path)
        mixer.music.load(str(self.path))
        mixer.music.play()


class Album:
    def __init__(self, path, cover_art_file):
        self.tracks = []
        self.current_index = 0
        self.title = path.stem
        self.art = Image.open(path / cover_art_file)
        self.thumb = self.art.resize((DISPLAY_W // 2, DISPLAY_H // 2))
        source = list(path.glob("*.mp3"))
        for file in list(source):
            self.tracks.append(Track(file))

    @property
    def current_track(self):
        return self.tracks[self.current_index]

    def next(self):
        self.current_index += 1
        self.current_index %= len(self.tracks)

    def prev(self):
        self.current_index -= 1
        self.current_index %= len(self.tracks)


class Library:
    def __init__(self, root):
        self.albums = []
        self.current_index = 0
        source = list(root.rglob("cover.png"))
        source.extend(root.rglob("cover.jpg"))
        for file in source:
            title = file.parts[-2]
            self.albums.append(Album(file.parents[0], file.name))

    @property
    def current_album(self):
        return self.albums[self.current_index]

    def next(self):
        self.current_index += 1
        self.current_index %= len(self.albums)

    def prev(self):
        self.current_index -= 1
        self.current_index %= len(self.albums)


view = "album"

def main():
    global view

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTONS, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    display = ST7789(
        rotation=90,
        port=0,
        cs=1,
        dc=9,
        backlight=13,
        spi_speed_hz=80 * 1000 * 1000
    )

    canvas = Image.new("RGB", (240, 240), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    music_path = root.parents[0] / "music"
    print(f"Loading music from {music_path}")
    library = Library(music_path)

    def handle_button(pin):
        global view
        label = LABELS[BUTTONS.index(pin)]
        if view == "album":
            if label == "B":
                library.prev()
            if label == "Y":
                library.next()
            if label == "X":
                view = "track"
        if view == "track":
            if label == "A":
                view = "album"
            if label == "B":
                library.current_album.current_track.play()
            if label == "X":
                library.current_album.prev()
            if label == "Y":
                library.current_album.next()

    for pin in BUTTONS:
        GPIO.add_event_detect(pin, GPIO.FALLING, handle_button, bouncetime=250)

    while True:
        draw.rectangle((0, 0, DISPLAY_W, DISPLAY_H), (0, 0, 0))

        selected_album = library.current_index

        if view == "album":
            offset_x = (DISPLAY_W // 4) - ((DISPLAY_W // 2) * selected_album)
            
            item = 0
            for album in library.albums:
                canvas.paste(album.thumb, (offset_x + (120 * item), 60), None)
                item += 1

            text_in_rect(draw, library.current_album.title, font, (26, DISPLAY_H - 60, DISPLAY_W - 26, DISPLAY_H), line_spacing=1.1, textcolor=(255, 255, 255))

            icon(canvas, icon_backdrop.rotate(180), (DISPLAY_W - 26, 47), (255, 255, 255))
            icon(canvas, icon_return.rotate(180), (DISPLAY_W - 20, 50), (0, 0, 0))

            icon(canvas, icon_backdrop, (0, DISPLAY_H - 73), (255, 255, 255))
            icon(canvas, icon_rightarrow.rotate(180), (0, DISPLAY_H - 70), (0, 0, 0))

            icon(canvas, icon_backdrop.rotate(180), (DISPLAY_W - 26, DISPLAY_H - 73), (255, 255, 255))
            icon(canvas, icon_rightarrow, (DISPLAY_W - 20, DISPLAY_H - 70), (0, 0, 0))

        elif view == "track":
            album = library.current_album
            selected_track = album.current_index

            item = 0
            offset_y = (DISPLAY_H // 2) - 12

            offset_y -= selected_track * 24

            for track in album.tracks:
                position_y = offset_y + item * 24
                draw.rectangle((0, position_y, DISPLAY_W, position_y + 24), fill=(5, 5, 5) if item % 2 else (9, 9, 9))

                if track == album.current_track:
                    draw.text((5, 1 + position_y), track.title, font=font, fill=(255, 255, 255))
                else:
                    draw.text((5, 1 + position_y), track.title, font=font, fill=(64, 64, 64))
                item += 1

            text_in_rect(draw, album.title, font, (0, 0, DISPLAY_W, 30), line_spacing=1.1, textcolor=(255, 255, 255))

            icon(canvas, icon_backdrop, (0, 47), (255, 255, 255))
            icon(canvas, icon_return, (0, 53), (0, 0, 0))

            icon(canvas, icon_backdrop.rotate(180), (DISPLAY_W - 26, 47), (255, 255, 255))
            icon(canvas, icon_rightarrow.rotate(90), (DISPLAY_W - 20, 50), (0, 0, 0))

            icon(canvas, icon_backdrop.rotate(180), (DISPLAY_W - 26, DISPLAY_H - 73), (255, 255, 255))
            icon(canvas, icon_rightarrow.rotate(-90), (DISPLAY_W - 20, DISPLAY_H - 70), (0, 0, 0))


        display.display(canvas)
        time.sleep(1.0 / 30)

    return 1