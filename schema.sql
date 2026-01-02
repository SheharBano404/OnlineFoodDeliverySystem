CREATE DATABASE IF NOT EXISTS food_aggregator
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

USE food_aggregator;

-- USERS
CREATE TABLE IF NOT EXISTS users (
  user_id       INT AUTO_INCREMENT PRIMARY KEY,
  full_name     VARCHAR(120) NOT NULL,
  email         VARCHAR(255) NOT NULL UNIQUE,
  phone_number  VARCHAR(30)  NOT NULL UNIQUE,
  type          ENUM('Admin','Customer','Delivery Agent','Restaurant Owner') NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  address       VARCHAR(255) NULL,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- RESTAURANTS
CREATE TABLE IF NOT EXISTS restaurants (
  restaurant_id INT AUTO_INCREMENT PRIMARY KEY,
  owner_id      INT NULL,
  name          VARCHAR(140) NOT NULL,
  address       VARCHAR(255) NOT NULL,
  status        ENUM('Active','Inactive') NOT NULL DEFAULT 'Active',
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_rest_owner
    FOREIGN KEY (owner_id) REFERENCES users(user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  INDEX idx_rest_owner (owner_id),
  INDEX idx_rest_status (status)
) ENGINE=InnoDB;

-- MENU ITEMS
CREATE TABLE IF NOT EXISTS menu_items (
  menu_id       INT AUTO_INCREMENT PRIMARY KEY,
  restaurant_id INT NOT NULL,
  name          VARCHAR(160) NOT NULL,
  price         DECIMAL(10,2) NOT NULL,
  category      ENUM('Food','Drink') NULL,
  availability  TINYINT(1) NOT NULL DEFAULT 1,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_menu_restaurant
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  INDEX idx_menu_restaurant (restaurant_id),
  INDEX idx_menu_avail (availability),
  INDEX idx_menu_cat (category)
) ENGINE=InnoDB;

-- ORDERS
CREATE TABLE IF NOT EXISTS orders (
  order_id              INT AUTO_INCREMENT PRIMARY KEY,
  user_id               INT NOT NULL,
  restaurant_id         INT NOT NULL,
  status                ENUM('Placed','Accepted','Preparing','Out for Delivery','Delivered','Cancelled')
                        NOT NULL DEFAULT 'Placed',
  payment_method        ENUM('COD','Online') NOT NULL,
  delivery_instructions VARCHAR(255) NULL,

  placed_at             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  accepted_at           TIMESTAMP NULL,
  preparing_at          TIMESTAMP NULL,
  out_for_delivery_at   TIMESTAMP NULL,
  delivered_at          TIMESTAMP NULL,
  cancelled_at          TIMESTAMP NULL,

  CONSTRAINT fk_orders_user
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  CONSTRAINT fk_orders_restaurant
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,

  INDEX idx_orders_user (user_id),
  INDEX idx_orders_restaurant (restaurant_id),
  INDEX idx_orders_status (status)
) ENGINE=InnoDB;

-- ORDER ITEMS
CREATE TABLE IF NOT EXISTS order_items (
  orderitem_id      INT AUTO_INCREMENT PRIMARY KEY,
  order_id          INT NOT NULL,
  menu_item_id      INT NOT NULL,
  quantity          INT NOT NULL,
  price_at_purchase DECIMAL(10,2) NOT NULL,
  CONSTRAINT fk_orderitems_order
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_orderitems_menu
    FOREIGN KEY (menu_item_id) REFERENCES menu_items(menu_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  INDEX idx_orderitems_order (order_id)
) ENGINE=InnoDB;

-- DELIVERY ASSIGNMENTS
CREATE TABLE IF NOT EXISTS delivery_assignments (
  delivery_id       INT AUTO_INCREMENT PRIMARY KEY,
  order_id          INT NOT NULL UNIQUE,
  delivery_agent_id INT NOT NULL,
  status            ENUM('Assigned','Pickup','Dropped') NOT NULL DEFAULT 'Assigned',
  assigned_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  pickup_at         TIMESTAMP NULL,
  dropped_at        TIMESTAMP NULL,
  expected_drop_at  TIMESTAMP NULL,
  CONSTRAINT fk_delivery_order
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_delivery_agent
    FOREIGN KEY (delivery_agent_id) REFERENCES users(user_id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  INDEX idx_delivery_agent (delivery_agent_id)
) ENGINE=InnoDB;

-- ORDER STATUS HISTORY (timeline)
CREATE TABLE IF NOT EXISTS order_status_history (
  history_id   INT AUTO_INCREMENT PRIMARY KEY,
  order_id     INT NOT NULL,
  status       VARCHAR(40) NOT NULL,
  actor_user_id INT NULL,
  note         VARCHAR(255) NULL,
  created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_hist_order
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_hist_actor
    FOREIGN KEY (actor_user_id) REFERENCES users(user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  INDEX idx_hist_order (order_id),
  INDEX idx_hist_created (created_at)
) ENGINE=InnoDB;

-- DELIVERY LOCATION UPDATES (basic tracking)
CREATE TABLE IF NOT EXISTS delivery_locations (
  location_id INT AUTO_INCREMENT PRIMARY KEY,
  delivery_id INT NOT NULL,
  lat         DECIMAL(10,7) NOT NULL,
  lng         DECIMAL(10,7) NOT NULL,
  note        VARCHAR(255) NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_loc_delivery
    FOREIGN KEY (delivery_id) REFERENCES delivery_assignments(delivery_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_loc_delivery (delivery_id),
  INDEX idx_loc_created (created_at)
) ENGINE=InnoDB;

-- ORDER TOTALS VIEW
CREATE OR REPLACE VIEW v_order_totals AS
SELECT
  o.order_id,
  o.user_id,
  o.restaurant_id,
  o.status,
  o.placed_at,
  COALESCE(SUM(oi.quantity * oi.price_at_purchase), 0.00) AS total
FROM orders o
LEFT JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY o.order_id;

DELIMITER $$

DROP TRIGGER IF EXISTS trg_orders_user_must_be_customer $$
CREATE TRIGGER trg_orders_user_must_be_customer
BEFORE INSERT ON orders
FOR EACH ROW
BEGIN
  IF (SELECT type FROM users WHERE user_id = NEW.user_id) <> 'Customer' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only Customers can place orders';
  END IF;
END $$

DROP TRIGGER IF EXISTS trg_delivery_agent_must_be_agent $$
CREATE TRIGGER trg_delivery_agent_must_be_agent
BEFORE INSERT ON delivery_assignments
FOR EACH ROW
BEGIN
  IF (SELECT type FROM users WHERE user_id = NEW.delivery_agent_id) <> 'Delivery Agent' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'delivery_agent_id must be a Delivery Agent';
  END IF;
END $$

DELIMITER ;