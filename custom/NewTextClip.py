from PIL import Image, ImageDraw, ImageFont
import numpy as np

from moviepy.video.VideoClip import ImageClip


def get_text_position(align, canvas_size, text_size, margin):
    center = canvas_size[0] / 2, canvas_size[1] / 2
    # Shift text up and left so that it is centered
    text_center = center[0] - text_size[0] / 2, center[1] - text_size[1] / 2

    align = align.lower()
    if align == "center":
        text_position = text_center
    elif align in ("north", "top"):
        text_position = text_center[0], margin
    elif align in ("south", "bottom"):
        text_position = text_center[0], canvas_size[1] - margin - text_size[1]
    elif align in ("west", "left"):
        text_position = margin, text_center[1]
    elif align in ("east", "right"):
        text_position = canvas_size[0] - margin - text_size[0], text_center[1]
    elif align in ("northwest", "topleft"):
        text_position = margin, margin
    elif align in ("northeast", "topright"):
        text_position = canvas_size[0] - margin - text_size[0], margin
    elif align in ("southeast", "bottomright"):
        text_position = (
            canvas_size[0] - margin - text_size[0],
            canvas_size[1] - margin - text_size[1],
        )
    elif align in ("southwest", "bottomleft"):
        text_position = margin, canvas_size[1] - margin - text_size[1]
    else:
        raise ValueError("The parameter `align` does not contain a valid string")
    return text_position


class NewTextClip(ImageClip):
    """Class for autogenerated text clips.

    Creates an ImageClip originating from a script-generated text image.
    Requires ImageMagick.

    Parameters
    -----------

    text
      A string of the text to write. Can be replaced by argument
      ``filename``.

    filename
      The name of a file in which there is the text to write,
      as a string or a path-like object.
      Can be provided instead of argument ``txt``

    size
      Size of the picture in pixels. Can be auto-set if
      method='label', but mandatory if method='caption'.
      the height can be None, it will then be auto-determined.

    bg_color
      Color of the background. See ``TextClip.list('color')``
      for a list of acceptable names.

    color
      Color of the text. See ``TextClip.list('color')`` for a
      list of acceptable names.

    font
      Name of the font to use. See ``TextClip.list('font')`` for
      the list of fonts you can use on your computer.

    stroke_color
      Color of the stroke (=contour line) of the text. If ``None``,
      there will be no stroke.

    stroke_width
      Width of the stroke, in pixels. Can be a float, like 1.5.

    align
      center | East | West | South | North . Will only work if ``method``
      is set to ``caption``

    transparent
      ``True`` (default) if you want to take into account the
      transparency in the image.

    """

    def __init__(
        self,
        text=None,
        filename=None,
        size=None,
        color="black",
        bg_color="transparent",
        fontsize=None,
        font=None,
        font_index=None,
        stroke_color=None,
        stroke_width=1,
        text_position=None,
        align="center",
        spacing=4,
        margin=0,
        justify="center",
        transparent=True,
    ):
        if font is None:
            pil_font = ImageFont.load_default()
        else:
            if font_index is None:
                pil_font = ImageFont.truetype(font, fontsize)
            else:
                pil_font = ImageFont.truetype(font, fontsize, font_index)

        if text is not None and filename is not None:
            raise ValueError(
                "Both `text` and `filename` cannot be set simultaneously"
            )
        if text is None:
            with open(filename, "r") as file:
                text = file.read()

        # Create a temporary image to get the size of the rendered text
        bg_image = Image.new("RGB", (1, 1), color=(0, 0, 0))
        draw = ImageDraw.Draw(bg_image)
        text_size = draw.textsize(
            text, font=pil_font, stroke_width=stroke_width, spacing=spacing
        )

        size = size or text_size

        if text_position is not None and align is not None:
            raise ValueError(
                "Both `text_position` and `align` cannot be set simultaneously"
            )
        if text_position is None:
            text_position = get_text_position(align, size, text_size, margin)

        bg_image = Image.new("RGB", size, color=bg_color)
        draw = ImageDraw.Draw(bg_image)

        draw.text(
            text_position,
            text,
            font=pil_font,
            fill=color,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
            align=justify,
            spacing=spacing,
        )

        ImageClip.__init__(self, np.array(bg_image), transparent=transparent)
        self.text = text
        self.color = color

        """

        cmd = [
            IMAGEMAGICK_BINARY,
            "-background",
            bg_color,
            "-fill",
            color,
            "-font",
            font,
        ]

        if fontsize is not None:
            cmd += ["-pointsize", "%d" % fontsize]
        if kerning is not None:
            cmd += ["-kerning", "%0.1f" % kerning]
        if stroke_color is not None:
            cmd += ["-stroke", stroke_color, "-strokewidth", "%.01f" % stroke_width]
        if size is not None:
            cmd += ["-size", "%sx%s" % (size[0], size[1])]
        if align is not None:
            cmd += ["-gravity", align]
        if interline is not None:
            cmd += ["-interline-spacing", "%d" % interline]

        if tempfilename is None:
            tempfile_fd, tempfilename = tempfile.mkstemp(suffix=".png")
            os.close(tempfile_fd)

        cmd += [
            "%s:%s" % (method, txt),
            "-type",
            "truecolormatte",
            "PNG32:%s" % tempfilename,
        ]

        if print_cmd:
            print(" ".join(cmd))

        try:
            subprocess_call(cmd, logger=None)
        except (IOError, OSError) as err:
            error = (
                f"MoviePy Error: creation of {filename} failed because of the "
                f"following error:\n\n{err}.\n\n."
                "This error can be due to the fact that ImageMagick "
                "is not installed on your computer, or (for Windows "
                "users) that you didn't specify the path to the "
                "ImageMagick binary. Check the documentation."
            )
            raise IOError(error)

        self.stroke_color = stroke_color

        if remove_temp:
            if os.path.exists(tempfilename):
                os.remove(tempfilename)
            if os.path.exists(temptxt):
                os.remove(temptxt)
        

    @staticmethod
    def list(arg):
        \"""Returns a list of all valid entries for the ``font`` or ``color`` argument of
        ``TextClip``\"""

        popen_params = {"stdout": sp.PIPE, "stderr": sp.DEVNULL, "stdin": sp.DEVNULL}

        if os.name == "nt":
            popen_params["creationflags"] = 0x08000000

        process = sp.Popen(
            [IMAGEMAGICK_BINARY, "-list", arg], encoding="utf-8", **popen_params
        )
        result = process.communicate()[0]
        lines = result.splitlines()

        if arg == "font":
            # Slice removes first 8 characters: "  Font: "
            return [l[8:] for l in lines if l.startswith("  Font:")]
        elif arg == "color":
            # Each line is of the format "aqua  srgb(0,255,255)  SVG" so split on space and take
            # the first item to get the color name.
            # The first 5 lines are header information, not colors, so ignore
            return [l.split(" ")[0] for l in lines[5:]]
        else:
            raise Exception("Moviepy Error: Argument must equal 'font' or 'color'")

    @staticmethod
    def search(string, arg):
        \"""Returns the of all valid entries which contain ``string`` for the
           argument ``arg`` of ``TextClip``, for instance

           >>> # Find all the available fonts which contain "Courier"
           >>> print(TextClip.search('Courier', 'font'))

        \"""
        string = string.lower()
        names_list = TextClip.list(arg)
        return [name for name in names_list if string in name.lower()]
    """