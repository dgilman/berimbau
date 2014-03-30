from ctypes import *
from ctypes.util import find_library
from ctypes import sizeof as c_sizeof
import errno
import time

libc = CDLL(find_library('c'), use_errno=True)

# hardcoded macosx constants!
CTL_NET = 4
PF_ROUTE = 17
NET_RT_IFLIST2 = 6

RTM_IFINFO2 = 0x12
IFF_LOOPBACK = 0x8
AF_LINK = 18

class timeval32(Structure):
   _fields_ = [('tv_sec', c_int32),
               ('tv_usec', c_int32)]

class if_data64(Structure):
   _pack_ = 4
   _fields_ = [('ifi_type', c_ubyte),
               ('ifi_typelen', c_ubyte),
               ('ifi_physical', c_ubyte),
               ('ifi_addrlen', c_ubyte),
               ('ifi_hdrlen', c_ubyte),
               ('ifi_recvquota', c_ubyte),
               ('ifi_xmitquota', c_ubyte),
               ('ifi_unused1', c_ubyte),
               ('ifi_mtu', c_uint32),
               ('ifi_metric', c_uint32),
               ('ifi_baudrate', c_uint64),
               ('ifi_ipackets', c_uint64),
               ('ifi_ierrors', c_uint64),
               ('ifi_opackets', c_uint64),
               ('ifi_oerrors', c_uint64),
               ('ifi_collisions', c_uint64),
               ('ifi_ibytes', c_uint64),
               ('ifi_obytes', c_uint64),
               ('ifi_imcasts', c_uint64),
               ('ifi_omcasts', c_uint64),
               ('ifi_iqdrops', c_uint64),
               ('ifi_noproto', c_uint64),
               ('ifi_recvtiming', c_uint32),
               ('ifi_xmittiming', c_uint32),
               ('ifi_lastchange', timeval32)]

class if_msghdr2(Structure):
   _fields_ = [('ifm_msglen', c_ushort),
               ('ifm_version', c_ubyte),
               ('ifm_type', c_ubyte),
               ('ifm_addrs', c_int),
               ('ifm_flags', c_int),
               ('ifm_index', c_ushort),
               ('ifm_snd_len', c_int),
               ('ifm_snd_maxlen', c_int),
               ('ifm_snd_drops', c_int),
               ('ifm_timer', c_int),
               ('ifm_data', if_data64)]

class sockaddr_dl(Structure):
   _fields_ = [('sdl_len', c_ubyte),
               ('sdl_family', c_ubyte),
               ('sdl_index', c_ushort),
               ('sdl_type', c_ubyte),
               ('sdl_nlen', c_ubyte),
               ('sdl_alen', c_ubyte),
               ('sdl_slen', c_ubyte),
               ('sdl_data', c_char * 12)] # for now

MIB_TYPE = c_int * 6
mib = MIB_TYPE(CTL_NET, PF_ROUTE, 0, 0, NET_RT_IFLIST2, 0)

def query_if(ifname):
   ifname = ifname.encode('ascii')
   sysctl_buf_len = c_uint(0)

   rval = libc.sysctl(mib, 6, None, byref(sysctl_buf_len), None, 0)
   if rval != 0:
      raise Exception(errno.errorcode[get_errno()])

   sysctl_buf = create_string_buffer(sysctl_buf_len.value)
   rval = libc.sysctl(mib, 6, sysctl_buf, byref(sysctl_buf_len), None, 0)
   if rval != 0:
      raise Exception(errno.errorcode[get_errno()])

# walk the structure.  you need to know the length from ifm_msglen
   idx = addressof(sysctl_buf)
   end = idx + sysctl_buf_len.value
   while idx < end:
      batch_off = idx - addressof(sysctl_buf)
      ifmsg = cast(c_void_p(idx), POINTER(if_msghdr2))
      if ifmsg.contents.ifm_type != RTM_IFINFO2:
         idx += ifmsg.contents.ifm_msglen
         continue
      if ifmsg.contents.ifm_flags & IFF_LOOPBACK:
         idx += ifmsg.contents.ifm_msglen
         continue
      # 12 bytes to compensate for 32 bit alignment
      sdl = cast(c_void_p(idx + c_sizeof(if_msghdr2)), POINTER(sockaddr_dl))
      if sdl.contents.sdl_family != AF_LINK:
         idx += ifmsg.contents.ifm_msglen
         continue

      if ifname != sdl.contents.sdl_data[0:sdl.contents.sdl_nlen]:
         idx += ifmsg.contents.ifm_msglen
         continue
      return ifmsg.contents.ifm_data.ifi_ibytes, ifmsg.contents.ifm_data.ifi_obytes
      #idx += ifmsg.contents.ifm_msglen
   raise Exception('ifname {0} not found'.format(ifname))

def bw_rate(ifname, delay=1):
   first_ibytes, first_obytes = query_if(ifname)
   time.sleep(delay)
   second_ibytes, second_obytes = query_if(ifname)

   ikb_s = ((second_ibytes - first_ibytes) / (1024. * delay))
   okb_s = ((second_obytes - first_obytes) / (1024. * delay))
   return ikb_s, okb_s

if __name__ == '__main__':
   while True:
      print(bw_rate('en1'))
