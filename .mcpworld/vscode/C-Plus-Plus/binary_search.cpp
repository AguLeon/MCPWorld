#include <iostream> // For input/output operations
#include <vector>   // For using std::vector

// Function to perform binary search on a sorted vector
int binarySearch(const std::vector<int>& arr, int target) {
    int low = 0;
    int high = arr.size() - 1;

    while (low <= high) {
        int mid = low + (high - low) / 2; // Calculate middle index

        if (arr[mid] == target) {
            return mid; // Target found, return its index
        } else if (arr[mid] < target) {
            low = mid + 1; // Target is in the right half
        } else {
            high = mid - 1; // Target is in the left half
        }
    }

    return -1; // Target not found
}

int main() {
    std::vector<int> sortedArray = {1, 3, 5, 7, 9, 11, 13, 15, 17, 19};
    int targetValue = 13;

    int result = binarySearch(sortedArray, targetValue);

    if (result != -1) {
        std::cout << "Target value " << targetValue << " found at index: " << result << std::endl;
    } else {
        std::cout << "Target value " << targetValue << " not found in the array." << std::endl;
    }

    targetValue = 6; // Test with a value not in the array
    result = binarySearch(sortedArray, targetValue);

    if (result != -1) {
        std::cout << "Target value " << targetValue << " found at index: " << result << std::endl;
    } else {
        std::cout << "Target value " << targetValue << " not found in the array." << std::endl;
    }

    return 0;
}
