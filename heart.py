#!/usr/bin/env python3

import turtle

def draw_heart():
    screen = turtle.Screen()
    screen.bgcolor("white")
    screen.title("Heart Painter")

    # Create a turtle object
    heart = turtle.Turtle()
    heart.shape("turtle")
    heart.color("red")
    heart.speed(3)

    # Start drawing the heart
    heart.begin_fill()
    heart.left(50)
    heart.forward(133)
    heart.circle(50, 200)
    heart.right(140)
    heart.circle(50, 200)
    heart.forward(133)
    heart.end_fill()

    # Hide the turtle
    heart.hideturtle()

    # Keep the window open
    screen.mainloop()

def draw_human_heart():
    screen = turtle.Screen()
    screen.bgcolor("white")
    screen.title("Human Heart Painter")

    # Create a turtle object
    heart = turtle.Turtle()
    heart.speed(5)
    heart.color("red")

    # Draw the main heart shape (irregular and organic)
    heart.penup()
    heart.goto(0, -200)
    heart.pendown()
    heart.begin_fill()
    heart.left(140)
    heart.forward(180)
    heart.circle(-90, 200)
    heart.setheading(60)
    heart.circle(-50, 200)
    heart.setheading(200)
    heart.forward(120)
    heart.setheading(140)
    heart.circle(-50, 100)
    heart.setheading(220)
    heart.forward(100)
    heart.setheading(320)
    heart.circle(-90, 100)
    heart.setheading(60)
    heart.forward(180)
    heart.end_fill()

    # Draw arteries (blue lines)
    heart.penup()
    heart.goto(-50, 100)
    heart.pendown()
    heart.color("blue")
    heart.width(3)
    heart.setheading(60)
    heart.forward(50)
    heart.backward(50)
    heart.setheading(120)
    heart.forward(50)
    heart.backward(50)

    heart.penup()
    heart.goto(50, 100)
    heart.pendown()
    heart.setheading(120)
    heart.forward(50)
    heart.backward(50)
    heart.setheading(60)
    heart.forward(50)
    heart.backward(50)

    # Draw veins (dark red lines)
    heart.penup()
    heart.goto(0, 50)
    heart.pendown()
    heart.color("darkred")
    heart.width(2)
    heart.setheading(90)
    heart.circle(30, 180)

    heart.penup()
    heart.goto(-30, 70)
    heart.pendown()
    heart.setheading(120)
    heart.circle(20, 180)

    # Hide the turtle
    heart.hideturtle()

    # Keep the window open
    screen.mainloop()

if __name__ == "__main__":
    draw_human_heart()