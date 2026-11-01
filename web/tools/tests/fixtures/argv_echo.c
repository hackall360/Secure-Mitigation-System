#include <stdio.h>
#include <string.h>
void echo_arg(const char*a){char buf[64];strcpy(buf,a);printf(buf);puts("");}
int main(int c,char**v){if(c>1)echo_arg(v[1]);return 0;}
