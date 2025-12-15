import ast,glob
files=glob.glob('migrations/versions/*.py')
revs={}
downs={}
for f in files:
    with open(f,'r',encoding='utf-8') as fh:
        txt=fh.read()
    rev=None; down=None
    for line in txt.splitlines():
        line=line.strip()
        if line.startswith('revision') and '=' in line:
            rev= line.split('=',1)[1].strip().strip("\"' ")
        if line.startswith('down_revision') and '=' in line:
            v=line.split('=',1)[1].strip()
            try:
                down=ast.literal_eval(v)
            except Exception:
                down=None
    if rev:
        revs[rev]=f
    if down is not None:
        if isinstance(down,tuple):
            for d in down:
                downs.setdefault(d,[]).append(rev)
        else:
            downs.setdefault(down,[]).append(rev)

print('Revisions:', sorted(revs.keys()))
print('Referenced as down_revision:', sorted([k for k in downs.keys() if k is not None]))
heads=[r for r in revs.keys() if r not in downs]
print('Heads:', heads)
