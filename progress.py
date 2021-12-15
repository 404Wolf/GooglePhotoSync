from cursor import show, hide
from time import time
from math import floor


class spinner:
    """
    Class for progress spinner

    Attributes:
        state: current status of progress bar (/, |, \, -)
    """

    def __init__(self, msg, hide_cursor=True):
        """
        Create the progress spinner, with the initial message and the spinner afterwards.

        Args:
            msg: message to send while progress is loading
            hide_cursor: hide the console cursor
        Returns:
            None
        """

        self.msg = msg  # message to send before each updated spin
        self.hide_cursor = hide_cursor  # to or to not hide the cursor

        self.start = time()  # start UNIX time
        self.states = ["\\", "|", "/", "-"]  # all possible spinner states
        self.state = 0  # current state of spinner

        if self.hide_cursor:
            hide()

        self.next()

    def next(self):
        """
        Progress the spinner
        """
        # tick the current state of the spinner
        self.state += 1
        if self.state == 4:
            self.state = 0

        print(
            self.msg
            + self.states[self.state]
            + " "
            + "{:.2f}".format(time() - self.start)
            + "s",
            end="\r",
        )

    def finish(self, msg):
        """
        Replaces spinner with end message

        Args:
            msg: message to close off with
        Returns:
            None
        """

        print(" " * (len(self.msg) + 1), end="\r")
        print(self.msg)
        print(msg, end="\n\n")

        if self.hide_cursor:
            show()


class bar:
    """
    Class for progress bar

    Attributes:
        state: count from 0 to max of the progress bar's status
        total: total for when progress bar finishes
        width: number of characters wide progress bar is
        ticks: number of ticks to give progress bar
    """

    def __init__(self, msg, hide_cursor=True, width=40, fill="#", total=100):
        """
        Create the progress spinner, with the initial message and the spinner afterwards.

        Args:
            msg: message to send while progress is loading
            hide_cursor: hide the console cursor
            width: number of ticks to give progress bar when maxed
            fill: what to fill in the bar with
            total: max score for completion
        Returns:
            None
        """

        self.msg = msg  # message to send before each updated bar
        self.hide_cursor = hide_cursor  # to or to not hide the cursor
        self.width = width  # number of ticks to give progress bar when maxed
        self.fill = fill  # what to fill in the bar with
        self.total = total  # max score for completion

        self.start = time()  # start UNIX time
        self.state = 0  # current state of bar

        if self.hide_cursor:
            hide()

        self.next()

    def next(self, ticks=1):
        """
        Ticks the progress bar forward

        Args:
            ticks: how many ticks to move it along
        Returns:
            None
        Raises:
            OverFlowError: when the progress bar has finished and has hit the end
        """

        self.state += ticks  # tick the bar forward

        if self.state > self.total + 1:
            raise OverflowError("Progress bar total has been hit")

        # calculate how many ticks, and round to the lowest int
        filled_units = floor(self.state / self.total * self.width)
        unfilled_units = (
            self.width - filled_units
        )  # calculate how many whitespace characters

        # convert to strings
        filled_units = filled_units * self.fill
        unfilled_units = unfilled_units * " "

        # calc eta
        try:
            eta = time() - self.start  # elapsed time since object creation
            eta = eta / self.state  # average time per state change
            eta = eta * (self.total - self.state)  # time for states left
            eta = "{:.2f}".format(eta)
        except ZeroDivisionError:
            eta = 0

        print(
            self.msg + "|" + filled_units + unfilled_units + "| " + str(eta) + "s",
            end="\r",
        )  # output current state of progress bar

    def finish(self, msg):
        """
        Skip to end of progress bar
        """

        self.state = self.total  # set current state to last tick
        print(msg + ((self.width - len(msg) + 20) * " "))
