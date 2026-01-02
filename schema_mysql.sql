CREATE DATABASE IF NOT EXISTS food_aggregator
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE food_aggregator;

-- USERS
CREATE TABLE IF NOT EXISTS users (
  user_id       INT AUTO_INCREMENT PRIMARY KEY,
  full_name     VARCHAR(120) NOT NULL,
  email         VARCHAR(255) NOT NULL UNIQUE,
  phone_number  VARCHAR(30)  NOT NULL UNIQUE,
  type          ENUM('Admin','Customer','Delivery Agent') NOT NULL,
  address       VARCHAR(255) NULL,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- RESTAURANTS
CREATE TABLE IF NOT EXISTS restaurants (
  restaurant_id INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(140) NOT NULL,
  address       VARCHAR(255) NOT NULL,
  status        ENUM('Active','Inactive') NOT NULL DEFAULT 'Active',
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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
  CONSTRAINT chk_menu_price CHECK (price >= 0),
  CONSTRAINT chk_menu_availability CHECK (availability IN (0,1))
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
  INDEX idx_orders_restaurant (restaurant_id)
) ENGINE=InnoDB;

-- ORDER ITEMS (captures price at purchase)
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

  INDEX idx_orderitems_order (order_id),
  CONSTRAINT chk_orderitems_qty CHECK (quantity > 0),
  CONSTRAINT chk_orderitems_price CHECK (price_at_purchase >= 0)
) ENGINE=InnoDB;

-- DELIVERY ASSIGNMENTS (1:1 per order via UNIQUE)
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

-- REVIEWS (polymorphic: exactly one target set)
CREATE TABLE IF NOT EXISTS reviews (
  review_id         INT AUTO_INCREMENT PRIMARY KEY,
  reviewer_id       INT NOT NULL,
  restaurant_id     INT NULL,
  delivery_agent_id INT NULL,
  rating            TINYINT NOT NULL,
  comment           TEXT NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_reviews_reviewer
    FOREIGN KEY (reviewer_id) REFERENCES users(user_id)
    ON DELETE CASCADE ON UPDATE CASCADE,

  CONSTRAINT fk_reviews_restaurant
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  CONSTRAINT fk_reviews_agent
    FOREIGN KEY (delivery_agent_id) REFERENCES users(user_id)
    ON DELETE SET NULL ON UPDATE CASCADE,

  CONSTRAINT chk_reviews_rating CHECK (rating BETWEEN 1 AND 5),
  CONSTRAINT chk_reviews_polymorphic CHECK (
    (restaurant_id IS NOT NULL AND delivery_agent_id IS NULL)
    OR
    (restaurant_id IS NULL AND delivery_agent_id IS NOT NULL)
  )
) ENGINE=InnoDB;

-- VIEW: order totals from captured purchase prices
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

-- TRIGGERS: enforce role integrity
DELIMITER $$

CREATE TRIGGER trg_orders_user_must_be_customer
BEFORE INSERT ON orders
FOR EACH ROW
BEGIN
  IF (SELECT type FROM users WHERE user_id = NEW.user_id) <> 'Customer' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Only Customers can place orders';
  END IF;
END$$

CREATE TRIGGER trg_delivery_agent_must_be_agent
BEFORE INSERT ON delivery_assignments
FOR EACH ROW
BEGIN
  IF (SELECT type FROM users WHERE user_id = NEW.delivery_agent_id) <> 'Delivery Agent' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'delivery_agent_id must be a Delivery Agent';
  END IF;
END$$

CREATE TRIGGER trg_review_agent_target_must_be_agent
BEFORE INSERT ON reviews
FOR EACH ROW
BEGIN
  IF NEW.delivery_agent_id IS NOT NULL THEN
    IF (SELECT type FROM users WHERE user_id = NEW.delivery_agent_id) <> 'Delivery Agent' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Review target must be a Delivery Agent';
    END IF;
  END IF;
END$$

DELIMITER ;