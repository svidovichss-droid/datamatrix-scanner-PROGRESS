# Icons Directory

This directory contains icon files for the DataMatrix Scanner application.

## Required Files

- `app.ico` - Main application icon (Windows .ico format)
  - Recommended sizes: 16x16, 32x32, 48x48, 256x256 pixels
  - Used for EXE file icon and window icon

## Creating an Icon

You can create an icon using:
1. Online converters: https://www.icoconverter.com/
2. Graphic tools: GIMP, Photoshop with ICO plugin
3. Command line: `convert input.png -define icon:auto-resize=256,128,64,48,32,16 output.ico`

## Note

The `app.ico` file is a placeholder. Replace it with your actual icon before building the production EXE.
