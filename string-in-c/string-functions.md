# การใช้งานฟังก์ชันเกี่ยวกับ String ในภาษา C

# stdio.h

# ฟังก์ชันรับข้อมูล

1. scanf("%s", str)
- ใช้รับข้อมูล string จากผู้ใช้
- หยุดรับเมื่อเจอช่องว่าง
- ต้องระวังเรื่อง buffer overflow

2. gets(str) (ไม่แนะนำให้ใช้)
- รับข้อมูลทั้งบรรทัด
- ไม่ปลอดภัยเนื่องจากไม่มีการตรวจสอบขนาด buffer

3. fgets(str, size, stdin)
- รับข้อมูลทั้งบรรทัดอย่างปลอดภัย
- กำหนดขนาดสูงสุดที่รับได้
- เก็บ newline character ไว้ด้วย



# ฟังก์ชันแสดงผล

1. printf("%s", str)
- แสดงผล string
- สามารถกำหนดความกว้างและการจัดวางได้
2. puts(str)
- แสดงผล string พร้อมขึ้นบรรทัดใหม่
- ใช้งานง่ายกว่า printf



# stdlib.h
1. atoi(str)
- แปลง string เป็นจำนวนเต็ม
- คืนค่า 0 ถ้าแปลงไม่ได้
  
2. atof(str)
- แปลง string เป็นจำนวนทศนิยม
- คืนค่า 0.0 ถ้าแปลงไม่ได้

3. atol(str)
- แปลง string เป็น long integer
- คืนค่า 0 ถ้าแปลงไม่ได้

4. string.h
- ฟังก์ชันคำนวณความยาว
  
5. strlen(str)
- นับความยาวของ string
- ไม่นับ null terminator
- คืนค่าเป็น size_t



# ฟังก์ชันคัดลอก

1. strcpy(dest, src)
- คัดลอก src ไปยัง dest
- ไม่ตรวจสอบขนาด buffer

2. strncpy(dest, src, n)
- คัดลอกไม่เกิน n ตัวอักษร
- ปลอดภัยกว่า strcpy



# ฟังก์ชันต่อ string

1. strcat(dest, src)
- ต่อ src ท้าย dest
- ไม่ตรวจสอบขนาด buffer

2. strncat(dest, src, n)
- ต่อไม่เกิน n ตัวอักษร
- ปลอดภัยกว่า strcat



# ฟังก์ชันเปรียบเทียบ

1. strcmp(str1, str2)
- เปรียบเทียบ str1 กับ str2
- คืนค่า 0 ถ้าเหมือนกัน
- คืนค่า < 0 ถ้า str1 < str2
- คืนค่า > 0 ถ้า str1 > str2

2. strncmp(str1, str2, n)
- เปรียบเทียบ n ตัวแรก
- การคืนค่าเหมือน strcmp



# ฟังก์ชันค้นหา

1. strchr(str, ch)
- หาตำแหน่งแรกของอักขระ ch
- คืนค่า NULL ถ้าไม่พบ

2. strstr(haystack, needle)
- หา substring (needle) ใน string หลัก (haystack)
- คืนค่า NULL ถ้าไม่พบ
