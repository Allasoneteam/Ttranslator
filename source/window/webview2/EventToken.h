#ifndef TTW_COMPAT_EVENTTOKEN_H
#define TTW_COMPAT_EVENTTOKEN_H
#ifdef _WIN32

// WebView2.h includes "EventToken.h" from the Windows SDK. Depending on the MinGW-w64 version this header is missing
// (Ubuntu 22.04) or present as "eventtoken.h" (file names are case-sensitive when cross-compiling on Linux). This
// stand-in gives the one type WebView2.h needs; it is the compatibility header of the webview library
// (compatibility/mingw/include/EventToken.h, MIT, https://github.com/webview/webview).

#ifndef __eventtoken_h__

#ifdef __cplusplus
#include <cstdint>
#else
#include <stdint.h>
#endif

typedef struct EventRegistrationToken {
  int64_t value;
} EventRegistrationToken;
#endif // __eventtoken_h__

#endif // _WIN32
#endif // TTW_COMPAT_EVENTTOKEN_H
