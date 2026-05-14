"""Reference conversations for the eval suite.

Each entry is a single user turn against a fresh session. The eval
runner invokes the agent for each, captures the result and message
trail, and feeds them to the evaluators.

`expected_tool` is consumed by the rule-based tool_efficiency
evaluator. `none` means the prompt should be answered without any tool
call (graceful-degradation path in the baseline prompt).
"""

REFERENCE_CONVERSATIONS = [
    {
        "id": "q1_honeymoon_availability",
        "user_message": "Is the honeymoon suite available the first weekend in June?",
        "expected_tool": "check_room_availability",
    },
    {
        "id": "q2_price_diff",
        "user_message": "What's the price difference between a standard room and a deluxe suite?",
        "expected_tool": "check_room_availability",
    },
    {
        "id": "q3_late_checkout",
        "user_message": "Can I get a late checkout?",
        "expected_tool": "none",
    },
    {
        "id": "q4_room_service_menu",
        "user_message": "What's on the room service menu?",
        "expected_tool": "get_room_service_menu",
    },
    {
        "id": "q5_vegetarian",
        "user_message": "Do you have a vegetarian option for dinner?",
        "expected_tool": "get_room_service_menu",
    },
    {
        "id": "q6_walking_distance",
        "user_message": "What are the best restaurants within walking distance?",
        "expected_tool": "get_local_recommendations",
    },
    {
        "id": "q7_family",
        "user_message": "I have kids — is there anything nearby for families?",
        "expected_tool": "get_local_recommendations",
    },
    {
        "id": "q8_pool_hours",
        "user_message": "What time does the pool open?",
        "expected_tool": "none",
    },
    {
        "id": "q9_table_booking",
        "user_message": "Can you book me a table at the rooftop bar?",
        "expected_tool": "none",
    },
    {
        "id": "q10_compare_suites",
        "user_message": "Compare a junior suite and the presidential suite for a 3-night stay",
        "expected_tool": "check_room_availability",
    },
]
