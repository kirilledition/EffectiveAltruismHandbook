with open(".github/workflows/build.yml", "r") as f:
    data = f.read()

data = data.replace("""<<<<<<< HEAD
        if: steps.diff.outputs.changed == 'true'
        uses: actions/upload-artifact@v4
=======
        uses: actions/upload-artifact@v7.0.0
>>>>>>> c88df2a (update deps and bump python to 3.14)""", """        if: steps.diff.outputs.changed == 'true'
        uses: actions/upload-artifact@v7.0.0""")

with open(".github/workflows/build.yml", "w") as f:
    f.write(data)
