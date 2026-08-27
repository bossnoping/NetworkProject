#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void demonstrateInput(void);
void demonstrateOutput(void);
void demonstrateStdlib(void);
void demonstrateStringH(void);

int main() {
    printf("\n=== String Functions Demo ===\n\n");
    
    demonstrateInput();
    demonstrateOutput();
    demonstrateStdlib();
    demonstrateStringH();
    
    return 0;
}

void demonstrateInput(void) {
    char str[50];
    printf("=== Input Functions ===\n");
    
    // scanf demonstration
    printf("Enter a string (scanf): ");
    scanf("%s", str);
    printf("scanf result: %s\n", str);
    
    // Clear input buffer
    while (getchar() != '\n');
    
    // fgets demonstration
    printf("Enter a string (fgets): ");
    fgets(str, sizeof(str), stdin);
    printf("fgets result: %s", str);
    
    printf("\n");
}

void demonstrateOutput(void) {
    char str[] = "Hello";
    printf("\n=== Output Functions ===\n");
    
    // printf demonstration
    printf("printf output: %s\n", str);
    
    // puts demonstration
    printf("puts output: ");
    puts(str);
    
    printf("\n");
}

void demonstrateStdlib(void) {
    printf("=== Stdlib Functions ===\n");
    
    // atoi demonstration
    char str1[] = "123";
    int num1 = atoi(str1);
    printf("atoi(\"%s\") = %d\n", str1, num1);
    
    // atof demonstration
    char str2[] = "45.67";
    double num2 = atof(str2);
    printf("atof(\"%s\") = %.2f\n", str2, num2);
    
    // atol demonstration
    char str3[] = "123456789";
    long num3 = atol(str3);
    printf("atol(\"%s\") = %ld\n", str3, num3);
    
    printf("\n");
}

void demonstrateStringH(void) {
    printf("=== String.h Functions ===\n");
    
    // strlen demonstration
    char str[] = "Hello";
    size_t length = strlen(str);
    printf("strlen(\"%s\") = %zu\n", str, length);
    
    // String copy demonstrations
    char dest[50];
    char src[] = "Hello";
    
    strcpy(dest, src);
    printf("strcpy result: %s\n", dest);
    
    strncpy(dest, src, 3);
    dest[3] = '\0';
    printf("strncpy(3 chars) result: %s\n", dest);
    
    // String concatenation demonstrations
    char concat_dest[50] = "Hello";
    char concat_src[] = " World";
    
    strcat(concat_dest, concat_src);
    printf("strcat result: %s\n", concat_dest);
    
    strcpy(concat_dest, "Hello");  // Reset dest
    strncat(concat_dest, concat_src, 3);
    printf("strncat(3 chars) result: %s\n", concat_dest);
    
    // String comparison demonstrations
    char comp_str1[] = "apple";
    char comp_str2[] = "banana";
    printf("strcmp(\"apple\", \"banana\") = %d\n", strcmp(comp_str1, comp_str2));
    
    char comp_str3[] = "apple";
    char comp_str4[] = "appetite";
    printf("strncmp(\"apple\", \"appetite\", 3) = %d\n", strncmp(comp_str3, comp_str4, 3));
    
    // String search demonstrations
    char search_str[] = "Hello";
    char *chr_result = strchr(search_str, 'e');
    if (chr_result != NULL) {
        printf("strchr: 'e' found at position %ld\n", chr_result - search_str);
    }
    
    char haystack[] = "Hello World";
    char needle[] = "World";
    char *str_result = strstr(haystack, needle);
    if (str_result != NULL) {
        printf("strstr: Found \"%s\" in \"%s\"\n", needle, haystack);
    }
}
