#include <iostream>
#include <vector> // Using vector for dynamic array

void bubbleSort(std::vector<int>& arr) {
    int n = arr.size();
    bool swap_check; // Flag to optimize the sort: if no swaps in a pass, array is sorted

    for (int i = 0; i < n - 1; ++i) {
        swap_check = false; // Reset swapped flag for each pass
        for (int j = 0; j < n - 1 - i; ++j) {
            // Compare adjacent elements
            if (arr[j] > arr[j + 1]) {
                // Swap if they are in the wrong order
                std::swap(arr[j], arr[j + 1]);
                swap_check = true; // Indicate a swap occurred
            }
        }
        // If no two elements were swapped by inner loop, then array is sorted
        if (!swap_check) {
            break;
        }
    }
}

int main() {
    std::vector<int> numbers = {64, 34, 25, 12, 22, 11, 90};

    std::cout << "Original array: ";
    for (int num : numbers) {
        std::cout << num << " ";
    }
    std::cout << std::endl;

    bubbleSort(numbers);

    std::cout << "Sorted array: ";
    for (int num : numbers) {
        std::cout << num << " ";
    }
    std::cout << std::endl;

    return 0;
}

