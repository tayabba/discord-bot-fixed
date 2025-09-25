import random,string,time
class KeyGenerator:
    @staticmethod
    def generate_key(months,amount):
        m = hex(months)[2:].zfill(2).upper()
        a = hex(amount)[2:].zfill(2).upper()
        chars = string.ascii_uppercase + string.digits
        s1 = ''.join(random.choices(chars,k=5))
        s2 = m + a + ''.join(random.choices(chars,k=3))
        s3 = ''.join(random.choices(chars,k=5))
        return f"{s1}-{s2}-{s3}"
    
    @staticmethod 
    def validate_key(key):
        try:
            if not key or len(key)!=17:
                return False,0,0
            s = key.split('-')
            if len(s)!=3 or any(len(x)!=5 for x in s):
                return False,0,0
            m = int(s[1][:2],16)
            a = int(s[1][2:4],16)
            return True,m,a
        except:
            return False,0,0