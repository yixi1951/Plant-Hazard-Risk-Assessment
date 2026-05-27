import os, shutil, sys
src_default = r"C:\Users\ASUS\AppData\Local\Temp\tb_runs"
src = sys.argv[1] if len(sys.argv) > 1 else src_default
dst = os.path.join(os.getcwd(), 'runs')
if not os.path.exists(src):
    print('source not found:', src); sys.exit(1)
dst_full = os.path.join(dst, os.path.basename(src)) if os.path.basename(src) else dst
if os.path.exists(dst_full):
    # if exists, remove to replace
    shutil.rmtree(dst_full)
shutil.copytree(src, dst_full)
print('copied to', dst_full)
