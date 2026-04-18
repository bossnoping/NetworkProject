public class StatUtil {
    public static int countNegative(Measurable[] objects) {
        int count = 0;
        for (Measurable obj : objects) {
            if (obj.getMeasure() < 0) {
                count++;
            }
        }
        return count;
    }

    public static void sort(int[] a) {
        for (int i = 0; i < a.length - 1; i++) {// i แบ่งส่วนเรียงแล้วกับยังไม่เรียง
            int minPos = i;
            for (int j = i + 1; j < a.length; j++) { // วนลูปหาค่าน้อยสุด
                if (a[j] < a[minPos]) {
                    minPos = j;
                }
            }
            // สลับข้อมูลใน minPos และ i ทําให้ข้อมูลใน minPos ไปอยู่ส่วนที่เรียงแล้ว
            int temp = a[minPos];
            a[minPos] = a[i];
            a[i] = temp;
        }
    }
}
