import { useEffect, useState } from "react";
import { API_BASE_URL } from "./api";

const API_URL = API_BASE_URL;

function Notifications({ token, userRole, onOpenBooking }) {
  const [notifications, setNotifications] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  async function loadNotifications() {
    if (!token) return;

    setLoading(true);

    try {
      const response = await fetch(
        `${API_URL}/my/notifications`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error(
          "Could not load notifications."
        );
      }

      const data = await response.json();

      setNotifications(
        Array.isArray(data) ? data : []
      );
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadNotifications();
  }, [token]);


  async function markAsRead(notificationId) {
  try {
    const response = await fetch(
      `${API_URL}/my/notifications/${notificationId}/read`,
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) {
      throw new Error("Could not mark notification as read.");
    }

    const updatedNotification = await response.json();

    setNotifications((current) =>
      current.map((notification) =>
        notification.notification_id === notificationId
          ? {
              ...notification,
              is_read: updatedNotification.is_read,
            }
          : notification
      )
    );

    return true;
  } catch (error) {
    console.error(error);
    return false;
  }
}

  async function handleNotificationClick(notification) {
  const wasUnread = !notification.is_read;

  if (wasUnread) {
    await markAsRead(notification.notification_id);
  }

  setOpen(false);

  if (
    (notification.notification_type === "booking" ||
      notification.notification_type === "payment") &&
    notification.related_booking_id &&
    onOpenBooking
  ) {
    onOpenBooking(
      notification.booking_context,
      notification.related_booking_id
    );
  }
}

  const unreadCount = notifications.filter(
    (notification) => !notification.is_read
  ).length;

  return (
    <div className="notification-wrapper">
      <button
        className="notification-button"
        onClick={() => {
          setOpen(!open);

          if (!open) {
            loadNotifications();
          }
        }}
        aria-label="Notifications"
      >
        🔔

        {unreadCount > 0 && (
          <span className="notification-badge">
            {unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="notification-panel">
          <div className="notification-header">
            <strong>
              Notifications
            </strong>

            {unreadCount > 0 && (
              <span>
                {unreadCount} unread
              </span>
            )}
          </div>

          {loading ? (
            <p className="notification-empty">
              Loading notifications...
            </p>
          ) : notifications.length === 0 ? (
            <p className="notification-empty">
              No notifications yet.
            </p>
          ) : (
            <div className="notification-list">
              {notifications.map(
                (notification) => (
                  <button
                    key={
                      notification.notification_id
                    }
                    className={`notification-item ${
                      notification.is_read
                        ? "read"
                        : "unread"
                    }`}
                    onClick={() =>
                      handleNotificationClick(
                        notification
                      )
                    }
                  >
                    <div className="notification-item-title">
                      {!notification.is_read && (
                        <span className="notification-dot">
                          ●
                        </span>
                      )}

                      {notification.title}
                    </div>

                    <p>
                      {notification.message}
                    </p>

                    <small>
                      {new Date(
                        notification.created_at
                      ).toLocaleString("en-IN")}
                    </small>

                    {userRole ===
                      "supplier" &&
                      notification.notification_type ===
                        "booking" &&
                      notification.related_booking_id &&
                      !notification.is_read && (
                        <span className="notification-action-hint">
                          View booking →
                        </span>
                      )}

                    {userRole === "farmer" &&
                      notification.related_booking_id &&
                      !notification.is_read && (
                        <span className="notification-action-hint">
                          View booking →
                        </span>
                      )}
                  </button>
                )
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default Notifications;
