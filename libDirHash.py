import os
import hashlib
import tempfile
import tarfile




def dirHash(dir) :
    # Use an absolute path.
    # Hash of relative/absolute paths would differ! (tar file)
    # Relative path: 
    # simon@lapL:/tmp$ tar tf tmpu*
    # bla/
    # bla/a
    # Absolute path:
    # simon@lapL:/tmp$ tar tf tmpc*
    # tmp/bla/
    # tmp/bla/a
    
    dir = os.path.abspath(dir)
    tmp = tempfile.mkstemp(suffix='.tar')
    tar = tarfile.TarFile(tmp[1], mode='w')
    tar.add(dir)
    tar.close()
    
    md5 = hashlib.md5()
    f = open(tmp[1])
    while True :
        s = f.read(1024)
        md5.update(s)
        if s == '' : break
    f.close()
    
    os.remove(tmp[1])
    
    return md5.hexdigest()
