#include <iostream>
#include <vector>

int get_size_of_linked_list(const std::vector<int> &values) {
    return values.size();
}

int main() {
    std::vector<int> sample {1, 2, 3, 4};
    std::cout << get_size_of_linked_list(sample) << std::endl;
    return 0;
}
