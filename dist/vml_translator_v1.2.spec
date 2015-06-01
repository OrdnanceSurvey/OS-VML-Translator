# -*- mode: python -*-
a = Analysis(['dist\vml_translator_v1.2.pyw'],
             pathex=['C:\'],
             hiddenimports=['osgeo._ogr', 'osgeo', 'osgeo._osr'],
             hookspath=None,
             runtime_hooks=None)

filepath = "C:\"

a.datas = []
for dirname, dirnames, filenames in os.walk(filepath):
    # add data files for all files in path and subdirs.
    for filename in filenames:
        a.datas += [ (filename, os.path.join(dirname, filename), 'DATA')] 


pyz = PYZ(a.pure)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='vml_translator_v1.2.exe',
          debug=False,
          strip=None,
          upx=True,
          console=False)
